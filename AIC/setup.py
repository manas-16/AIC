from setuptools import setup, find_packages

setup(
    name="aic-compiler",
    version="0.1.0",
    description="AI Compiler — compile .intent files to any target language",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Manas Khare",
    url="https://github.com/manas-16/AIC",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "aic": [
            "templates/*.template",
            "templates/*.json",
        ]
    },
    install_requires=[
        "click>=8.0.0",
        "colorama>=0.4.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "httpx>=0.24.0",
    ],
    extras_require={
        "claude": ["anthropic>=0.20.0"],
        "gemini": ["google-generativeai>=0.4.0"],
        "ollama": ["ollama>=0.1.0"],
    },
    entry_points={
        "console_scripts": [
            "aic=aic.main:cli",
        ]
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Code Generators",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
    ],
)
