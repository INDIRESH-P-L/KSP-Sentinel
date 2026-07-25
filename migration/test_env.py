import os
print("APP SAIL STARTING")
print("CATALYST_AUTH is string:", isinstance(os.getenv("CATALYST_AUTH"), str))
print("CATALYST_PROJECT_ID:", os.getenv("CATALYST_PROJECT_ID"))
