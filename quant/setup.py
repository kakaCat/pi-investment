from setuptools import setup, find_packages

setup(
    name="quantsys",
    version="1.0.0",
    description="量化交易系统 - 完整的Python量化交易框架",
    author="QuantTeam",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "akshare>=1.12.0",
        "scikit-learn>=1.3.0",
        "xgboost>=2.0.0",
        "lightgbm>=4.0.0",
        "optuna>=3.0.0",
        "apscheduler>=3.10.0",
        "psycopg2-binary>=2.9.9",
        "matplotlib>=3.7.0",
        "seaborn>=0.12.0",
        "tqdm>=4.65.0",
    ],
    entry_points={
        "console_scripts": [
            "quant=quantsys.cli.main:main",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
