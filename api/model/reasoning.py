from api.model.api_main import make_request_ollama_reasoning
from database.db import Upload, User, upload_file
import os

generate_prompt = lambda width, prompt: f"""
THINK LOUDLY!
1. Break the problem into {width} step alternatives to adress it
2. Choose one alternative
3. DO NOT USE CONJECTURES. Only use well known theorems, lemmas and mathematical concepts. 

PROBLEM: {prompt}

Do not write an answer yet, only propose the alternatives.
Use $$ for block math and $ for inline math.
"""

continue_prompt = lambda width: f"""
Now, extensively create an mathematical approximation using this alternative,
proposing {width} new ones from the result of the approach.

Remember: don't use any conjecture, only theorems, lemmas and other mathematical concepts well known.
If any solution encountered, return SOLVED, else *only return PROGRESS*
*Display math in $$ for block equations and $ for inline*
"""

article_prompt = lambda iterations: f"""
Now, write a detailed article about the problem in the logs and the solution, using the following structure:

1. Introduction: Briefly introduce the problem and its significance.
2. Problem Statement: Clearly state the problem and any assumptions.
3. Methodology: Describe the approach taken to solve the problem, including any algorithms or techniques used.
4. Results: Present the results of the solution, including any relevant data or visualizations.
5. Conclusion: Summarize the findings and discuss any implications or future work.

Render math in KATEX form.
MAKE SURE TO WRITE WITHIN THE NUMBER OF ITERATIONS BELLOW, AND FOR EACH STEP OF THE ITERATIONS,
WRITE A DISTINCT SECTION:
Iterations {iterations}
Current_iteration: 1
"""

article_prompt_continue = lambda iteration: f"""
Continue writing the article, expanding on the Methodology and Results sections.
Make sure to include any additional insights or observations that may be relevant.
Render math in KATEX form.
Current_iteration: {iteration}

"""

class Reasoning:
    def __init__(self, api_key:str, max_width:int, max_depth:int, model_name:str="deepseek-v3.1:671b-cloud", n_tokens_default:int=100000):
        self.max_width = max_width
        self.max_depth = max_depth
        self.model = model_name
        self.n_tokens_default = n_tokens_default
        self.api_key = api_key

    def reasoning_step(self, username:str, log_dir:str, query:str, init=False, prompt=None):
        #print(depth)
        print(os.path.join(log_dir, 'context.md'), username)
        obj_file = Upload.objects(filename__contains=os.path.join(log_dir, 'context.md'), creator=User.objects(username=username).first()).first()
        if not obj_file:
            raise ValueError("No context file found for reasoning step.")
        
        obj_response = Upload.objects(filename__contains=os.path.join(log_dir, 'response.md'), creator=User.objects(username=username).first()).first()
        if not obj_response:
            raise ValueError("No response file found for reasoning step.")

        def iterate():
            context = " "
            response = " "
            for i in range(self.max_depth):
                current_prompt = generate_prompt(self.max_width, query) if init or i == 0 else continue_prompt(self.max_width)
                r = make_request_ollama_reasoning(api_key=self.api_key, model_name=self.model, prompt=current_prompt, context=context, n_tokens=self.n_tokens_default)
                
                context += "\n\n" + current_prompt + "\n\n"

                for chunk in r:
                    if 'message' in chunk:
                        content = chunk['message'].get('content', '')
                        # accumulate into context while streaming
                        context += content
                        response += content

                        if "SOLVED" in content:
                            return "Solved the problem", 200

                        yield content
                


                upload_file(
                    user=User.objects(username=username).first(),
                    log_dir=log_dir,
                    filename='response.md',
                    raw_file=(response+"\n").encode('utf-8')
                )

                upload_file(
                    user=User.objects(username=username).first(),
                    log_dir=log_dir,
                    filename='context.md',
                    raw_file=(context+"\n").encode('utf-8')
                )

        return iterate(), 200

    def write_article(self, username:str, log_dir:str, iterations:int, n_tokens:int):
        def iterate():
            prev_generated = " "
            for i in range(iterations):                
                prompt = article_prompt(iterations) if i == 0 else article_prompt_continue(i+1)
                prev_generated += "\n\n" + prompt + "\n\n"
                r = make_request_ollama_reasoning(api_key=self.api_key, model_name=self.model, prompt=prompt, context=prev_generated, n_tokens=n_tokens)
                
                for chunk in r:
                    if 'message' in chunk:
                        content = chunk['message'].get('content', '')
                        # accumulate into context while streaming
                        prev_generated += content

                    yield content

                upload_file(
                    user=User.objects(username=username).first(),
                    log_dir=log_dir,
                    filename='article.md',
                    raw_file=prev_generated.encode('utf-8')
                )

        return iterate()
