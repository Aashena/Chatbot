import pytest
from QA_pipeline import QA_module


class TestQAModule:
    """Test suite for QA_module functionality."""

    @pytest.fixture
    def propastry_qa_module(self):
        """Fixture for propastry.ca namespace QA module."""
        return QA_module(name_space="propastry.ca")

    @pytest.fixture
    def biomonitoring_qa_module(self):
        """Fixture for bio-monitoring.ca namespace QA module."""
        return QA_module(name_space="bio-monitoring.ca")

    def test_website_content_readability(self, propastry_qa_module):
        """
        Test 1: Website content readability
        Verifies that the QA module can retrieve and use website content
        to answer questions about the website.
        """
        # Arrange
        query = "What is this website offering?"
        conv_history = ""

        # Act
        response = propastry_qa_module.ask(query, conv_history)

        # Assert
        assert response.source_type == "website_content", (
            f"Expected source_type to be 'website_content', "
            f"but got '{response.source_type}'"
        )
        assert response.is_valid is True, (
            f"Expected is_valid to be True, but got {response.is_valid}"
        )
        assert response.answer, "Expected a non-empty answer"

    def test_use_of_general_knowledge(self, biomonitoring_qa_module):
        """
        Test 2: Use of general knowledge
        Verifies that the QA module can use general knowledge to answer
        questions that aren't directly in the website content but are
        related to the conversation context.
        """
        # Arrange
        query = "What is a neural tube?"
        conv_history = (
            "User:What are the benefits of this product?\n"
            "Chatbot:This product helps prevent folate deficiency and neural "
            "tube defects when taken daily at least 12 weeks before and during "
            "early pregnancy, as part of a healthy diet."
        )

        # Act
        response = biomonitoring_qa_module.ask(query, conv_history)

        # Assert
        assert response.source_type == "general_knowledge", (
            f"Expected source_type to be 'general_knowledge', "
            f"but got '{response.source_type}'"
        )
        assert response.is_valid is True, (
            f"Expected is_valid to be True, but got {response.is_valid}"
        )
        assert response.answer, "Expected a non-empty answer"

    def test_unrelated_questions(self, biomonitoring_qa_module):
        """
        Test 3: Unrelated questions
        Verifies that the QA module appropriately refuses to answer
        questions that are unrelated to the website content and context.
        """
        # Arrange
        query = "Who is the president of the United States?"
        conv_history = ""

        # Act
        response = biomonitoring_qa_module.ask(query, conv_history)

        # Assert
        assert response.source_type == "none", (
            f"Expected source_type to be 'none', "
            f"but got '{response.source_type}'"
        )
        assert response.is_valid is False, (
            f"Expected is_valid to be False, but got {response.is_valid}"
        )
        assert response.reason, (
            "Expected a non-empty reason for refusing to answer"
        )
        assert isinstance(response.reason, str), (
            f"Expected reason to be a string, but got {type(response.reason)}"
        )

    # @pytest.mark.parametrize("namespace,query,expected_valid", [
    #     ("__propastry.ca____", "What is this website offering?", True),
    #     ("__bio-monitoring.ca____", "What is a neural tube?", True),
    #     ("__bio-monitoring.ca____", "Who is the president of the United States?", False),
    # ])
    # def test_parametrized_qa_responses(self, namespace, query, expected_valid):
    #     """
    #     Parametrized test for multiple scenarios.
    #     This test can be extended with additional test cases.
    #     """
    #     # Arrange
    #     qa_module = QA_module(namespace=namespace)
    #     conv_history = ""
    #     if "neural tube" in query:
    #         conv_history = (
    #             "User:What are the benefits of this product?\n"
    #             "Chatbot:This product helps prevent folate deficiency and neural "
    #             "tube defects when taken daily at least 12 weeks before and during "
    #             "early pregnancy, as part of a healthy diet."
    #         )

    #     # Act
    #     response = qa_module.ask(query, conv_history)

    #     # Assert
    #     assert response.is_valid == expected_valid, (
    #         f"Expected is_valid to be {expected_valid}, "
    #         f"but got {response.is_valid} for query: {query}"
    #     )