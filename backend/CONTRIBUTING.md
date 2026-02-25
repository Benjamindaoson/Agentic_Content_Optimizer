# Contributing to Growth Flywheel 2.5

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Qdrant 1.7+
- Git

### Setup Development Environment

```bash
# Fork and clone the repository
git clone https://github.com/your-username/growth-flywheel-2.5.git
cd growth-flywheel-2.5/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies

# Setup pre-commit hooks
pre-commit install

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
createdb growth_flywheel_dev
python migrate.py upgrade
```

## 📝 Code Style

### Python Style Guide
- Follow [PEP 8](https://pep8.org/)
- Use type hints for all functions
- Maximum line length: 100 characters
- Use docstrings for all public functions/classes

### Example

```python
async def generate_content(
    topic: str,
    category: str,
    num_candidates: int = 5
) -> List[ContentCandidate]:
    """
    Generate viral content candidates.

    Args:
        topic: Content topic
        category: Content category (e.g., "美妆", "穿搭")
        num_candidates: Number of candidates to generate

    Returns:
        List of content candidates with scores

    Raises:
        ValueError: If category is invalid
    """
    # Implementation
    pass
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_integration.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run only unit tests
pytest tests/ -m "not integration"
```

### Writing Tests

- Write tests for all new features
- Maintain test coverage above 60%
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)

```python
def test_content_generation_success():
    """Test successful content generation."""
    # Arrange
    generator = ViralGenerator(...)
    request = GenerationRequest(topic="test", category="美妆")

    # Act
    result = await generator.generate(request)

    # Assert
    assert len(result) > 0
    assert result[0].quality_score > 0.5
```

## 🔀 Pull Request Process

### Before Submitting

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, documented code
   - Add tests for new features
   - Update documentation if needed

3. **Run tests and linting**
   ```bash
   pytest tests/ -v
   black app/
   isort app/
   mypy app/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

Examples:
```
feat: add Self-RAG implementation
fix: resolve database connection leak
docs: update deployment guide
test: add integration tests for RAG system
```

### Submitting Pull Request

1. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request**
   - Go to GitHub and create a PR
   - Fill in the PR template
   - Link related issues

3. **PR Checklist**
   - [ ] Tests pass
   - [ ] Code follows style guide
   - [ ] Documentation updated
   - [ ] Commit messages follow convention
   - [ ] No merge conflicts

## 🐛 Reporting Bugs

### Before Reporting
- Check existing issues
- Verify it's reproducible
- Test on latest version

### Bug Report Template

```markdown
**Describe the bug**
A clear description of the bug.

**To Reproduce**
Steps to reproduce:
1. Call API endpoint '...'
2. With parameters '...'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.11.5]
- Version: [e.g., 2.5.0]

**Additional context**
Any other relevant information.
```

## 💡 Feature Requests

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Alternative solutions or features you've considered.

**Additional context**
Any other context or screenshots.
```

## 📚 Documentation

### Documentation Guidelines

- Update README.md for user-facing changes
- Update docstrings for code changes
- Add examples for new features
- Keep documentation concise and clear

### Building Documentation

```bash
# Generate API documentation
python -m pdoc app --html --output-dir docs/api

# Preview documentation
python -m http.server 8080 -d docs/
```

## 🔍 Code Review Process

### What We Look For

1. **Correctness**: Does it work as intended?
2. **Tests**: Are there adequate tests?
3. **Documentation**: Is it well documented?
4. **Style**: Does it follow our style guide?
5. **Performance**: Are there any performance concerns?
6. **Security**: Are there any security issues?

### Review Timeline

- Initial review: Within 2-3 days
- Follow-up reviews: Within 1-2 days
- Merge: After approval from maintainers

## 🎯 Areas for Contribution

### High Priority
- [ ] Additional LLM provider integrations
- [ ] Performance optimizations
- [ ] Test coverage improvements
- [ ] Documentation enhancements

### Medium Priority
- [ ] Redis caching implementation
- [ ] Real API integrations (Xiaohongshu, Weibo)
- [ ] Monitoring dashboard
- [ ] A/B testing framework

### Good First Issues
- [ ] Add more unit tests
- [ ] Improve error messages
- [ ] Fix typos in documentation
- [ ] Add code examples

## 📞 Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security**: Email security@example.com
- **Chat**: Join our Discord/Slack

## 🙏 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Given credit in documentation

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Growth Flywheel 2.5! 🚀
