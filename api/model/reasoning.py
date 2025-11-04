from api.model.api_main import make_request_ollama_reasoning
from api.model.upload_file import upload_file
import os

generate_prompt = lambda width: f"""
1. Break the problem into {width} step alternatives to adress it
2. Choose one alternative
3. DO NOT USE CONJECTURES. Only use well known theorems, lemmas and mathematical concepts. 

Do not write an answer yet, only propose the alternatives.
ALWAYS write math between \(\)s or \[\]s
"""

continue_prompt = lambda width: f"""
Now, extensively create an mathematical aproximation using this alternative,
proposing {width} new ones from the result of the approach.

Also, don't use any conjecture, only theorems, lemmas and other mathematical concepts well known.
return SOLVED at the and of the reponse, if there is found a solution
"""

class Reasoning:
    def __init__(self, max_width:int, max_depth:int, model_name:str="deepseek-v3.1:671b-cloud", n_tokens_default:int=100000):
        self.max_width = max_width,
        self.max_depth = max_depth
        self.model = model_name 
        self.n_tokens_default = n_tokens_default

    def reasoning_step(self, query:str, context:str, seq=None, init=True, depth=0, log_dir="log_dir_default"):
        if depth >= self.max_depth:
            return seq
        
        seq = [] if seq is None else seq
        
        prompt = ""
        prompt += f"PROBLEM: {query}\n\n"
        prompt += generate_prompt(self.max_width) if init else continue_prompt(self.max_width)

        print('PROMPT', prompt, context, self.model, self.n_tokens_default, log_dir)
        result = make_request_ollama_reasoning(model_name=self.model, prompt=prompt, context=context, n_tokens=self.n_tokens_default)
        context += "\n\n" + prompt

        if "SOLVED" in result:
            with open(os.path.join('/tmp', 'output.md'), 'wb') as file:
                file.write(result.encode('utf-8'))

            with open(os.path.join("/tmp", 'output.md'), 'rb') as file:
                upload_file(log_dir, 'output.md', file)

        
        with open(os.path.join("/tmp", f'log{depth}.md'), 'wb') as file:
            file.write(result.encode('utf-8'))
        
        with open(os.path.join("/tmp", f'log{depth}.md'), 'rb') as file:
            upload_file(log_dir, f'log{depth}.md', file)

        return self.reasoning_step(query=query, context=context+"\n\n"+result, seq=seq+[result], init=False, depth=depth+1, log_dir=log_dir)
        
        
