# Contributing to ClipStream

Thank you for your interest in contributing to ClipStream! We appreciate your time and effort in making this project better.

## 🚀 Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
   ```bash
   git clone git@github.com:your-username/ClipStream.git
   cd ClipStream
   ```
3. **Set up** the development environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements-dev.txt
   pre-commit install
   ```
4. **Create a branch** for your changes
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 🔧 Development Workflow

1. **Make your changes** following the project's coding standards
2. **Run tests** to ensure everything works
   ```bash
   pytest
   ```
3. **Commit your changes** with a descriptive message
   ```bash
   git commit -m "feat: add new feature"
   ```
4. **Push** to your fork
   ```bash
   git push origin feature/your-feature-name
   ```
5. **Open a Pull Request** from your fork to the main repository

## 📝 Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep lines under 88 characters (Black's default)
- Use absolute imports

## 🧪 Testing

- Write tests for all new features and bug fixes
- Ensure all tests pass before submitting a PR
- Use descriptive test function names
- Mock external dependencies in unit tests

## 📦 Versioning

We use [Semantic Versioning](https://semver.org/). For the versions available, see the [tags on this repository](https://github.com/aksaayyy/ClipStream/tags).

## 📜 License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

## 🙏 Acknowledgments

- Thanks to all contributors who have helped improve ClipStream!
