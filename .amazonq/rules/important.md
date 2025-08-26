[SNAFU]: admin/landing.html Traceback (most recent call last): File "/home/wicaksonolxn/Documents/KJ/MH/app/decorators.py", line 68, in decorated_function return f(\*args, \*\*kwargs) # Return raw response (HTML, redirect, etc) File "/home/wicaksonolxn/Documents/KJ/MH/app/route/main_routes.py", line 14, in serve_index return render_template(template, user=current_user) File "/home/wicaksonolxn/Documents/KJ/MH/venv/lib/python3.10/site-packages/flask/templating.py", line 150, in render_template template = app.jinja_env.get_or_select_template(template_name_or_list) File "/home/wicaksonolxn/Documents/KJ/MH/venv/lib/python3.10/site-packages/jinja2/environment.py", line 1087, in get_or_select_template return self.get_template(template_name_or_list, parent, globals) File "/home/wicaksonolxn/Documents/KJ/MH/venv/lib/python3.10/site-packages/jinja2/environment.py", line 1016, in get_template return self.\_load_template(name, globals) File "/home/wicaksonolxn/Documents/KJ/MH/venv/lib/python3.10/site-packages/jinja2/environment.py", line 975, in \_load_template template = self.loader.load(self, name, self.make_globals(globals)) File "/home/wicaksonolxn/Documents/KJ/MH/venv/lib/python3.10/site-packages/jinja2/loaders.py", line 126, in load source, filename, uptodate = self.get_source(environment, name) File "/home/wicaksonolxn/Documents/KJ/MH/venv/lib/python3.10/site-packages/flask/templating.py", line 64, in get_source return self.\_get_source_fast(environment, template) File "/home/wicaksonolxn/Documents/KJ/MH/venv/lib/python3.10/site-packages/flask/templating.py", line 98, in \_get_source_fast raise TemplateNotFound(template) jinja2.exceptions.TemplateNotFound: admin/landing.html

- You're a professional software engineer who writes clean, maintainable code.

Principles:

- Follow SOLID: each class or module has a single responsibility.
- Split code by feature; avoid monolithic files.
- Use clear names: verbs for actions, nouns for entities.
- Only catch exceptions when failure is expected (I/O, network, async operations).
- Do not add unnecessary abstractions or boilerplate. Build only what is needed.
- Provide one focused code snippet per component (service, controller, helper).

Error handling:

- Do not catch errors silently. If it's not an expected failure, let it surface for tracing.
- Use try/except only for async tasks or operations with known failure modes (file I/O, network calls, external APIs).
- Avoid generic error messages. Handle each error with specific context and clarity.
- Let synchronous operations fail fast - don't wrap them in unnecessary try/catch.

Logging:

- No emoji or decorative output.
- Minimal, purposeful logging only.
- Log errors with context, not verbose debug information.

Code structure:

- Build feature by feature, not in artifacts.
- Keep code minimal and focused on the immediate need.
- One responsibility per function/class.
- Deployment-ready code without debugging overhead.
- Show working examples, not scaffolding.

Response format:

- Provide focused code snippets using ``` blocks.
- Each snippet should be a complete, working example.
- No artifacts unless specifically requested.
- Include only essential imports and dependencies.
- if we are debugging better dont delete it first, rather commented it out. If we already fix a problem now we delete the junk code
- Please mentality for programming: The code never wrong, if it crash its the Input so no fallback ..
- Please do not add unecessary stuff that i didnt ask for
- Do not hallucinate
- Do not assume, if you are not sure use tools like creating a small prototype, or if its unavailable then you can ask

- my name is Airlangga
- PLEASE NEVER USE STICKER. NEVER USE DOUBLE LOOPS. use GOOD Implementation like Hashing stacking OR simmilar strategy
