from api.model.api_main import make_request_ollama_reasoning
from database.db import Upload, User
import os

generate_prompt = lambda problem, width: f"""
PROBLEM: {problem}

THINK LOUDLY!
1. Break the problem into {width} step alternatives to adress it
2. Choose one alternative
3. DO NOT USE CONJECTURES. Only use well known theorems, lemmas and mathematical concepts. 

Do not write an answer yet, only propose the alternatives.
Display math in KATEX form
"""

continue_prompt = lambda width: f"""
Now, extensively create an mathematical approximation using this alternative,
proposing {width} new ones from the result of the approach.

Remember: don't use any conjecture, only theorems, lemmas and other mathematical concepts well known.
If any solution encountered, return SOLVED, else *only return PROGRESS*
*Display math in KATEX form*
"""

article_prompt = lambda n_tokens_per_gen: f"""
From the given text, generate an article section with subsections to explain and formalize the reasoning process in detail.
The article should be approximately {n_tokens_per_gen} tokens long.
Use KATEX to display any math expressions.

For the first section, proceed as follows:
   1. Introduction: Briefly introduce the problem and its significance.
   2. Background: Provide necessary background information and definitions.

For subsequent sections, follow this structure:
   3. Methodology: Describe the reasoning steps taken to approach the problem.
   4. Results: Present the findings and any solutions derived from the reasoning process.
   5. Conclusion: Summarize the key points and implications of the results.

""" 

article_prompt_continue = lambda n_tokens_per_gen: f"""
Continue generating the article current section with subsections to explain and formalize the reasoning process in detail.
Also write the next sections of the article.
The article should be approximately {n_tokens_per_gen} tokens long.
Use KATEX to display any math expressions.
"""


class Reasoning:
    def __init__(self, api_key:str, max_width:int, max_depth:int, model_name:str="deepseek-v3.1:671b-cloud", n_tokens_default:int=100000):
        self.max_width = max_width
        self.max_depth = max_depth
        self.model = model_name 
        self.n_tokens_default = n_tokens_default
        self.api_key = api_key

    def reasoning_step(self, username:str, query:str, log_dir:str, init=True):        
        prompt = generate_prompt(query, self.max_width) if init else continue_prompt(self.max_width)
        user = User.objects(username=username).first()
        
        obj_context = Upload.objects(filename__contains=os.path.join(log_dir, 'context.md'), creator=user).first()
        self.context = obj_context.file.read().decode('utf-8') if obj_context is not None else ""

        # Request returns a stream/iterator of chunks
        r = make_request_ollama_reasoning(api_key=self.api_key, model_name=self.model, prompt=prompt, context=self.context, n_tokens=self.n_tokens_default)
        # add prompt to context first
        self.context += "\n\n" + prompt + "\n\n"
        obj_context.depth += 1

        def iterate():
            for chunk in r:
                if 'message' in chunk:
                    content = chunk['message'].get('content', '')
                    # accumulate into context while streaming
                    self.context += content
                    obj_context.file.replace(self.context.encode('utf-8'), content_type="text/markdown")
                    obj_context.save()

                    yield content

        return iterate()

    def generate_article_step(self, username:str, content:str, log_dir:str, iteration:int):
        user = User.objects(username=username).first()
        article_obj = Upload.objects(filename__contains=os.path.join(log_dir, 'article.md'), creator=user).first()
        anterior_generated = article_obj.file.read().decode('utf-8') if article_obj is not None else ""
        
        context = f"\n\nPREVIOUSLY GENERATED ARTICLE CONTENT:\n{self.anterior_generated}"
        prompt = article_prompt(self.n_tokens_default) if iteration == 0 else article_prompt_continue(self.n_tokens_default)
        prompt += f"\n\nCONTENT TO FORMALIZE:\n{content}\n\n"
        r = make_request_ollama_reasoning(api_key=self.api_key, model_name=self.model, prompt=prompt, context=context, n_tokens=self.n_tokens_default)

        def iterate(anterior_generated=anterior_generated):
            for chunk in r:
                if 'message' in chunk:
                    content = chunk['message'].get('content', '')
                    # accumulate into context while streaming
                    anterior_generated += content
                    article_obj.file.replace(anterior_generated.encode('utf-8'), content_type="text/markdown")
                    article_obj.save()

                    yield content


        return iterate()
