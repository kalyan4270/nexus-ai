from setuptools import setup, find_packages

setup(
    name="nexus-ai",
    version="1.0.0",
    py_modules=["cli", "main"],
    packages=find_packages(),
    install_requires=[
        "click",
        "rich",
        "fastapi",
        "langgraph",
        "groq",
        "neo4j",
        "gitpython",
        "mcp",
        "anthropic",
        "python-dotenv",
        "httpx",
        "pydantic"
    ],
    entry_points={
        "console_scripts": [
            "nexus=cli:cli"
        ]
    }
)