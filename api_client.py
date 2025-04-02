import base64
import logging
import threading
import time
import traceback
from typing import Dict, List, Optional, Union, Any

# OpenAI SDK import
from openai import OpenAI
import httpx

# Other imports
from PIL import Image
from PySide6.QtCore import QObject, Signal
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ApiClient(QObject):
    # Define signals for communication with UI
    output_update_signal = Signal(str)
    status_update_signal = Signal(str)
    
    # Static class variables to persist data between instances
    _last_problem_data = None
    _last_solution_content = None
    
    def __init__(self):
        """Initialize the API client"""
        super().__init__()
        self.start_time = time.time()
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
        
        # Initialize OpenAI client for OpenRouter
        if not self.openrouter_api_key:
            logger.error("OPENROUTER_API_KEY environment variable not set.")
            self.status_update_signal.emit("Error: OPENROUTER_API_KEY not set.")
            # Optionally raise an error or handle this case appropriately
            self.client = None 
        else:
            # Explicitly create an httpx client instance.
            # This respects environment variables like HTTP_PROXY/HTTPS_PROXY by default.
            http_client_instance = httpx.Client()

            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key,
                http_client=http_client_instance, # Pass the explicit client
            )
            # Optional OpenRouter headers for tracking/ranking
            self.openrouter_headers = {
                "HTTP-Referer": os.environ.get("OPENROUTER_REFERRER_URL", "acecoder.dev"), # Set env var OPENROUTER_REFERRER_URL
                "X-Title": os.environ.get("OPENROUTER_SITE_TITLE", "AceCoder"), # Set env var OPENROUTER_SITE_TITLE
            }
            logger.info("OpenAI client initialized for OpenRouter.")
        
        # Model configuration (using OpenRouter model names)
        self.model_name = "google/gemini-2.0-flash-thinking-exp:free" # Main model
        self.detection_model_name = "google/gemini-2.0-flash-lite-001" # Model for content detection
        self.temperature = 0.3  # Lower temperature for more deterministic outputs (lower preferred for coding questions)
        self.max_tokens = 8192   # Max tokens for OpenRouter (adjust as needed per model)
        
        # API request settings
        self.retry_count = 2    # Number of retries for failed API calls
        self.timeout = 120      # Timeout in seconds for API requests
        
        # State tracking
        self.last_solution_content = ApiClient._last_solution_content
        self.current_output_content = None
        self.last_raw_text = None
        
        # Log management
        self.max_log_size_mb = 50
        
        # No separate API configuration needed for OpenAI SDK
        # self.configure_api()
        
        self.prune_log_files()
        
        logger.info("API client initialized for OpenRouter")
    
    def prune_log_files(self):
        """Prune log files to prevent them from growing too large"""
        try:
            log_dir = os.path.dirname(os.path.abspath(__file__))
            for file in os.listdir(log_dir):
                if file.endswith('.log'):
                    file_path = os.path.join(log_dir, file)
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)  # Convert to MB
                    if size_mb > self.max_log_size_mb:
                        # Truncate log file to half its size
                        with open(file_path, 'r') as f:
                            content = f.read()
                        with open(file_path, 'w') as f:
                            f.write(content[len(content)//2:])
                        logger.info(f"Pruned log file {file} from {size_mb:.2f}MB to {size_mb/2:.2f}MB")
        except Exception as e:
            logger.warning(f"Failed to prune log files: {e}")

    def set_model_params(self, temperature=None, max_tokens=None):
        """Set generation parameters for the model"""
        if temperature is not None:
            self.temperature = float(temperature)
            logger.info(f"Model temperature set to: {self.temperature}")
        
        if max_tokens is not None:
            # Ensure max_tokens are within reasonable limits for the chosen model
            self.max_tokens = int(max_tokens)
            logger.info(f"Model max tokens set to: {self.max_tokens}")
            
    def process_images(self, image_data_list):
        """
        Process images using OpenAI SDK via OpenRouter
        
        Args:
            image_data_list: List of image data in bytes
        """
        if not self.client:
            logger.error("OpenAI client not initialized. Cannot process images.")
            self.status_update_signal.emit("Error: API Client not initialized.")
            return
            
        self.start_time = time.time()
        logger.debug(f"Starting processing timer at {self.start_time}")
        self.status_update_signal.emit("Processing screenshots...")
        
        encoded_images = [
            base64.b64encode(img).decode('utf-8')
            for img in image_data_list
        ]
        
        processing_thread = threading.Thread(
            target=self._process_images_thread,
            args=(encoded_images,),
            daemon=True
        )
        processing_thread.start()
    
    def _process_images_thread(self, encoded_images):
        """Thread function to process images via OpenRouter"""
        if not self.client:
            logger.error("OpenAI client not initialized. Cannot process images.")
            return
            
        try:
            total_images = len(encoded_images)
            self.status_update_signal.emit(f"Processing {total_images} image(s)...")
            
            content_type = self._detect_content_type(encoded_images)
            self.status_update_signal.emit(f"Detected content type: {content_type}")
            logger.info(f"Using prompt type: {content_type} for analysis")
            
            prompt = self._create_smart_prompt(total_images, content_type)
            self.status_update_signal.emit(f"Analyzing {content_type} problem with {self.model_name}...")

            # Prepare messages for OpenAI SDK multimodal format
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
            # Add images to the content list
            for encoded_image in encoded_images:
                # Format as data URI for base64 images
                image_url = f"data:image/jpeg;base64,{encoded_image}"
                messages[0]["content"].append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
                })

            prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
            logger.debug(f"Using prompt (preview): {prompt_preview}")
            logger.debug(f"Sending request to OpenRouter model: {self.model_name}")

            try:
                # Decide whether to stream based on a flag or setting (using stream=False for now)
                should_stream = True # Set this based on config or testing needs
                
                if should_stream:
                    stream = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        top_p=0.95,
                        stream=True,
                        extra_headers=self.openrouter_headers
                    )
                    
                    solution_content = ""
                    stream_start = time.time()
                    logger.debug(f"Solution streaming started at +{stream_start - self.start_time:.2f}s")
                    problem_title = f"# {content_type.title()} Analysis\n\n"
                    
                    for chunk in stream:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            solution_content += delta.content
                            self.output_update_signal.emit(problem_title + solution_content)
                            
                    # Final update after stream completes
                    self.last_solution_content = solution_content
                    ApiClient._last_solution_content = solution_content
                    self.last_raw_text = solution_content
                    ApiClient._last_raw_text = solution_content
                    
                    stream_end = time.time()
                    total_time = stream_end - self.start_time
                    self.status_update_signal.emit(f"Analysis complete in {total_time:.2f}s")
                    
                else: # Handle non-streaming response
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        top_p=0.95,
                        stream=False,
                        extra_headers=self.openrouter_headers
                    )
                    
                    request_end = time.time()
                    logger.debug(f"Non-streaming request completed at +{request_end - self.start_time:.2f}s")
                    
                    if response.choices:
                        solution_content = response.choices[0].message.content
                        problem_title = f"# {content_type.title()} Analysis\n\n"
                        self.output_update_signal.emit(problem_title + solution_content)
                        
                        # Store final solution
                        self.last_solution_content = solution_content
                        ApiClient._last_solution_content = solution_content
                        self.last_raw_text = solution_content
                        ApiClient._last_raw_text = solution_content
                        
                        total_time = request_end - self.start_time
                        self.status_update_signal.emit(f"Analysis complete in {total_time:.2f}s")
                    else:
                        logger.error("OpenRouter API request error: No response choices received.")
                        self.status_update_signal.emit("Error: No response choices received.")
                        
            except Exception as e:
                logger.error(f"OpenRouter API request error: {str(e)}")
                logger.error(traceback.format_exc())
                self.status_update_signal.emit(f"Error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in image processing thread: {str(e)}")
            logger.error(traceback.format_exc())
            self.status_update_signal.emit(f"Error processing images: {str(e)}")
    
    def _detect_content_type(self, encoded_images):
        """Detect content type using OpenAI SDK via OpenRouter (using flash model)"""
        if not self.client:
            logger.error("OpenAI client not initialized. Cannot detect content type.")
            return "general" # Default if client isn't ready

        try:
            first_image_data = encoded_images[0] if encoded_images else None
            if not first_image_data:
                logger.warning("No images provided for content detection")
                return "coding"
            
            self.status_update_signal.emit("Running content detection...")
            detection_prompt = """ONLY respond with one of these exact words based on what you see in the image:
- "coding" - if this shows a coding/programming problem or code snippet
- "multiple_choice" - if this shows a multiple choice question or quiz (including history, science, etc.)
- "debugging" - if this shows an error message or debugging scenario
- "system_design" - if this shows a system design/architecture problem
- "general" - if it doesn't clearly fit any of the above categories

RESPOND ONLY with the single most appropriate word from the list above, nothing else.
Example: If you see multiple choice history questions, respond with ONLY: multiple_choice"""
            
            # Prepare messages for OpenAI SDK multimodal format
            image_url = f"data:image/jpeg;base64,{first_image_data}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": detection_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }
            ]

            logger.debug(f"Sending detection request to OpenRouter model: {self.detection_model_name}")
            detection_response = self.client.chat.completions.create(
                model=self.detection_model_name, # Use the faster flash model
                messages=messages,
                temperature=0.1,
                max_tokens=10,
                top_p=0.95,
                stream=False, # No need to stream for detection
                extra_headers=self.openrouter_headers # Pass optional headers
            )
            
            raw_response = detection_response.choices[0].message.content.strip().lower()
            logger.debug(f"Raw detection response: '{raw_response}'")
            
            content_type = raw_response.replace('"', '').replace("'", "").strip('.')
            content_type = content_type.split()[0] if content_type else ""
            
            type_mapping = {
                "mcq": "multiple_choice", "quiz": "multiple_choice", "question": "multiple_choice",
                "questions": "multiple_choice", "test": "multiple_choice",
                "error": "debugging", "bug": "debugging", "issue": "debugging", "exception": "debugging",
                "program": "coding", "algorithm": "coding", "leetcode": "coding", "hackerrank": "coding",
                "design": "system_design", "architecture": "system_design", "diagram": "system_design"
            }
            
            if content_type in type_mapping:
                content_type = type_mapping[content_type]
            
            logger.info(f"Content type detected: {content_type}")
            
            valid_types = ["coding", "multiple_choice", "debugging", "system_design", "general"]
            if content_type not in valid_types:
                # Use secondary detection if primary fails
                secondary_content_type = self._secondary_content_detection(first_image_data)
                if secondary_content_type in valid_types:
                     logger.info(f"Using secondary detection result: {secondary_content_type}")
                     return secondary_content_type
                    
                logger.warning(f"Unknown content type detected: '{content_type}', defaulting to 'general'")
                return "general"
                
            return content_type
        
        except Exception as e:
            logger.error(f"Error in content type detection: {str(e)}")
            logger.error(traceback.format_exc())
            return "general"
            
    def _secondary_content_detection(self, encoded_image):
        """Fallback content detection using OpenAI SDK via OpenRouter"""
        if not self.client:
            logger.error("OpenAI client not initialized. Cannot run secondary detection.")
            return "general"

        try:
            self.status_update_signal.emit("Running secondary content detection...")
            logger.info("Using secondary content detection method")
            
            detection_prompt = """Analyze what's shown in this image and answer the following yes/no questions:
1. Does this image show multiple choice questions? (yes/no)
2. Does this image show programming code or a coding problem? (yes/no)
3. Does this image show error messages or debugging information? (yes/no)
4. Does this image show a system design diagram or architecture? (yes/no)

Format your response exactly like this example:
1. yes
2. no
3. no
4. no"""

            image_url = f"data:image/jpeg;base64,{encoded_image}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": detection_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }
            ]

            logger.debug(f"Sending secondary detection request to OpenRouter model: {self.detection_model_name}")
            detection_response = self.client.chat.completions.create(
                model=self.detection_model_name, # Use flash model
                messages=messages,
                temperature=0.1,
                max_output_tokens=50,
                top_p=0.95,
                stream=False,
                extra_headers=self.openrouter_headers
            )
            
            response_text = detection_response.choices[0].message.content.lower()
            logger.debug(f"Secondary detection response: {response_text}")
            
            yes_responses = []
            for i, line in enumerate(response_text.split('\n')):
                # Check more robustly for 'yes'
                clean_line = line.strip().lower()
                if clean_line.endswith('yes') or clean_line == 'yes':
                    yes_responses.append(i + 1)
            
            logger.debug(f"Secondary detection 'yes' answers for lines: {yes_responses}")

            if 1 in yes_responses: return "multiple_choice"
            if 2 in yes_responses: return "coding"
            if 3 in yes_responses: return "debugging"
            if 4 in yes_responses: return "system_design"
            return "general"
                
        except Exception as e:
            logger.error(f"Error in secondary content detection: {str(e)}")
            logger.error(traceback.format_exc())
            return "general"
    
    def _create_smart_prompt(self, num_images, content_type="coding"):
        """Create a smart prompt based on the number of images and detected content type"""
        
        # Base prompt components
        base_intro = "You are an expert coding assistant. "
        
        # Different prompt types
        prompts = {
            # Standard coding problem prompt (e.g., LeetCode, HackerRank)
            "coding": f"""Examine the screenshots of a programming problem and solve it.

Instructions:
1. Analyze the problem shown in the screenshots in detail
2. Provide a step-by-step approach to solving the problem
3. Include time and space complexity analysis
4. Implement an efficient solution in the language shown in the problem 
5. Use the EXACT function signature/template as provided in the problem
6. Do not add extra type hints or modify the signature
7. Add detailed comments explaining your solution
8. Provide a walkthrough of your solution with at least one example
9. Discuss any optimization techniques or potential edge cases

Your solution should be complete and ready to submit.""",

            # Debugging prompt - when screenshots likely contain error messages
            "debugging": f"""Examine the error/issue in the screenshots and provide a solution.

Instructions:
1. Identify the specific error or issue shown in the screenshots
2. Explain the root cause of the problem in detail
3. Provide a complete solution or fix for the issue
4. Include corrected code that resolves the problem
5. Explain your changes and why they fix the issue
6. Add defensive coding suggestions to prevent similar errors
7. If relevant, suggest optimizations or improvements beyond just fixing the error

Your explanation should be detailed enough for someone to understand both the problem and solution.""",

            # Multiple choice question prompt
            "multiple_choice": f"""Analyze the multiple choice question in the screenshots and determine the correct answer.

Instructions:
1. Identify the specific question being asked
2. Analyze each of the provided options thoroughly 
3. Explain the reasoning behind why each incorrect option is wrong
4. Provide a detailed explanation of why the correct option is right
5. CLEARLY state your final answer (e.g., "The correct answer is option C")
6. If applicable, include any relevant examples, definitions or context
7. For history/science/other factual questions, explain the factual background

Your answer should be confident and well-justified with clear reasoning.""",

            # Large codebase/system design problem prompt
            "system_design": f"""Analyze the system design problem shown in the screenshots and provide a comprehensive solution.

Instructions:
1. Understand the requirements and constraints of the system
2. Outline a high-level architecture with key components
3. Detail the data models and database schema if relevant
4. Explain API designs and communication patterns between components
5. Discuss scalability considerations and potential bottlenecks
6. Address security, reliability, and maintenance concerns
7. Provide diagrams or pseudo-code where helpful
8. Consider trade-offs in your design and explain your choices

Your solution should be comprehensive while being practical to implement.""",
        }
        
        # Default to the general prompt
        default_prompt = f"""Examine the screenshots and provide a detailed analysis and solution.

Instructions:
1. First, identify the type of problem or question being asked
2. Analyze the content thoroughly and methodically
3. Provide a clear, structured response that directly addresses the problem
4. Include code, diagrams, or step-by-step instructions as needed
5. Ensure your solution is complete and correct
6. Explain your reasoning and any assumptions you made

Your response should be well-structured with markdown headings and code blocks as appropriate."""

        # Special handling for multi-image scenarios
        if num_images > 3:
            multi_image_context = f"""
Note: There are {num_images} screenshots provided. These may represent:
- Multiple parts of a single problem
- A problem and its test cases
- Code and error messages
- Sequential steps in a larger problem

Ensure you consider all images together as a complete context before providing your solution."""
        else:
            multi_image_context = ""

        # Combine the components - use the detected content type prompt
        final_prompt = base_intro + prompts.get(content_type, default_prompt) + multi_image_context
        
        # Add universal guidelines
        universal_guidelines = """

UNIVERSAL GUIDELINES:
- Ensure your solution is correct and addresses all aspects of the problem
- Format your response with clear Markdown headings and sections
- Use proper code blocks with language tags for any code
- Be precise and avoid ambiguity in your explanations
- Write clean, efficient code that follows best practices
- Format code with proper indentation and readable style"""

        return final_prompt + universal_guidelines
    
    def process_followup(self, question_text):
        """Process a follow-up question using OpenAI SDK via OpenRouter"""
        if not self.client:
            logger.error("OpenAI client not initialized. Cannot process followup.")
            self.status_update_signal.emit("Error: API Client not initialized.")
            return

        # Check using last_solution_content, as last_raw_text persistence was unreliable
        if not self.last_solution_content:
            logger.warning("Follow-up requested, but self.last_solution_content is empty.")
            self.status_update_signal.emit("No previous analysis found to follow up on")
            return

        self.status_update_signal.emit(f"Processing follow-up request with {self.model_name}...")
        self.start_time = time.time()

        # Process directly in the calling thread (DirectWorkerThread in overlay.py)
        # Remove the extra thread creation here to fix timing issue
        # thread = threading.Thread(
        #     target=self._process_followup_thread,
        #     args=(question_text,),
        #     daemon=True
        # )
        # thread.start()
        self._process_followup_thread(question_text) # Call directly
    
    def _process_followup_thread(self, question_text):
        """Thread function to process follow-up questions via OpenRouter"""
        if not self.client:
            logger.error("OpenAI client not initialized. Cannot process followup.")
            return
            
        try:
            followup_type = self._categorize_followup(question_text)
            prompt = self._create_followup_prompt(question_text, followup_type)
            logger.debug(f"Using follow-up prompt type: {followup_type}")
            
            # Prepare messages for OpenAI format (no images in follow-up)
            messages = [
                {"role": "user", "content": prompt}
            ]

            try:
                logger.debug(f"Sending follow-up request to OpenRouter model: {self.model_name}")
                stream = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=0.95,
                    stream=True,
                    extra_headers=self.openrouter_headers
                )
            
                followup_content = "# Follow-up Response\n\n"
                solution_content = ""
                
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        solution_content += delta.content
                        self.output_update_signal.emit(followup_content + solution_content)
                
                total_time = time.time() - self.start_time
                self.status_update_signal.emit(f"Follow-up complete in {total_time:.2f}s")
            
            except Exception as e:
                logger.error(f"OpenRouter Follow-up error: {str(e)}")
                logger.error(traceback.format_exc())
                self.status_update_signal.emit(f"Error processing follow-up: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in follow-up thread: {str(e)}")
            self.status_update_signal.emit(f"Error: {str(e)}")
            
    def _categorize_followup(self, question_text):
        """Categorize the type of follow-up question"""
        question_lower = question_text.lower()
        
        # Check for specific follow-up types
        if any(term in question_lower for term in ['error', 'bug', 'fix', 'wrong', 'incorrect', 'not working']):
            return "error_fix"
        
        if any(term in question_lower for term in ['explain', 'clarify', 'help understand', 'how does']):
            return "explanation"
        
        if any(term in question_lower for term in ['optimize', 'faster', 'better', 'improve', 'efficient', 'performance']):
            return "optimization"
        
        if any(term in question_lower for term in ['alternative', 'other way', 'different approach', 'another solution']):
            return "alternative"
            
        # Default to general follow-up
        return "general"
    
    def _create_followup_prompt(self, question_text, followup_type):
        """Create a specialized follow-up prompt based on the type"""
        
        # Base context with previous solution (using last_solution_content)
        if not self.last_solution_content:
            # Fallback if somehow last_solution_content is empty
            logger.warning("Attempting to create follow-up prompt, but self.last_solution_content is empty.")
            # Provide a minimal context to avoid errors, though the result might be poor
            base_context = f"User's follow-up question: {question_text}\n\nProvide a general answer."
        else:
            base_context = f"""You previously analyzed a problem and provided this solution:

{self.last_solution_content}

User's follow-up question: {question_text}

"""

        # Specialized instructions based on follow-up type
        followup_instructions = {
            "error_fix": """Focus on identifying and fixing the specific error or issue mentioned. 
Provide a complete solution with corrected code and a detailed explanation of what was causing the problem.
Be precise about what changes need to be made and why they resolve the issue.""",
            
            "explanation": """Provide a clear, detailed explanation of the concept or aspect the user is asking about.
Use analogies, step-by-step breakdowns, or visual descriptions if helpful.
Make sure your explanation is accessible and tailored to help them genuinely understand the topic.""",
            
            "optimization": """Analyze the current solution and identify specific opportunities for optimization.
Explain the performance implications of your suggested improvements (time/space complexity).
Provide optimized code with comments explaining each optimization technique.
Compare before and after performance characteristics.""",
            
            "alternative": """Develop a completely different approach to solving the original problem.
Explain the key differences between this alternative and the previous solution.
Discuss the trade-offs between the approaches (simplicity, performance, readability, etc.).
Provide full implementation of the alternative solution.""",
            
            "general": """Address the user's follow-up question directly and thoroughly.
Provide any additional code, explanations, or resources needed to fully answer their question.
Make sure your response builds on the context of the previous solution while focusing specifically on what they're asking."""
        }
        
        # Build the final prompt
        final_prompt = base_context + followup_instructions.get(followup_type, followup_instructions["general"])
        
        return final_prompt

    def process_follow_up(self, question_text):
        """Compatibility method that calls process_followup to maintain UI compatibility"""
        return self.process_followup(question_text)