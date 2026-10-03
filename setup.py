from setuptools import setup, find_packages

setup(
    name="tui-llama-server",
    version="1.0.0",
    packages=find_packages(),
    package_data={"tui_llama_server": ["ui/*.tcss"]},
    include_package_data=True,
    install_requires=[
        "textual>=0.80.0",
        "rich>=13.0.0",
        "psutil>=5.9.0",
        "gguf>=0.10.0",
    ],
    entry_points={
        "console_scripts": [
            "tui-llama-server=tui_llama_server.cli:main",
        ],
    },
)
