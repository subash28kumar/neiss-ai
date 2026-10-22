# Contributing to NEISS-AI

Thank you for your interest in NEISS-AI. Questions, bug reports, ideas and code contributions are all welcome.

## Ask a question or report a problem

Open an issue at https://github.com/subash28kumar/neiss-ai/issues. Please include:

- what you were trying to do (for example, the question you typed or the command you ran);
- what you expected and what happened instead;
- the NEISS years and the version of NEISS-AI you used (`pip show neissai`).

If you use NEISS-AI in research, a report, a class or a presentation, I would be glad to hear about it. Use the "Share how you use it" link on the website, or open an issue.

## Suggest a feature

Open an issue that describes the use case: who would use the feature and what question it would answer.

## Contribute code

1. Fork the repository and create a branch for your change.
2. Install the package with test dependencies: `pip install -e ".[test]"`.
3. Make your change and add or update tests in `tests/`.
4. Run the tests: `pytest`.
5. Open a pull request that explains what the change does and why.

Please keep the method transparent: any change to how devices are labelled or how national estimates are computed should explain the reason and show its effect on the published estimates.

## Data and privacy

NEISS-AI uses only the public NEISS files from the US Consumer Product Safety Commission. Do not add any non-public data to issues, pull requests or the repository.

## Code of conduct

Be respectful and constructive. Harassment of any kind is not acceptable.
