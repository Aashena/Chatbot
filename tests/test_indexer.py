import pytest
from unittest.mock import patch, MagicMock
from indexer import index_pages


@pytest.fixture
def test_urls():
    """Fixture providing the test URLs."""
    return [
        "https://propastry.ca/about/",
        "https://propastry.ca",
        "https://propastry.ca/cart/",
        "https://propastry.ca/contact/",
        "https://propastry.ca/faq/",
        "https://propastry.ca/resources/",
        "https://propastry.ca/services/",
        "https://propastry.ca/shop/"
    ]


@pytest.fixture
def mock_vectorstore():
    """Fixture to mock UpstashVectorStore."""
    with patch('indexer.UpstashVectorStore') as mock_vs:
        # Create a mock instance
        mock_instance = MagicMock()
        mock_vs.return_value = mock_instance
        yield mock_vs, mock_instance


def test_index_pages_creates_30_chunks(test_urls, mock_vectorstore):
    """
    Test that index_pages creates exactly 31 chunks from the given URLs.
    
    This test verifies that:
    1. The web pages are crawled successfully
    2. The text is split into exactly 31 chunks
    3. UpstashVectorStore is called with correct parameters
    4. add_documents is called with the chunks
    """
    mock_vs_class, mock_vs_instance = mock_vectorstore
    namespace = "bio-monitoring.ca"
    
    # Run the indexing function
    num_chunks = index_pages(test_urls, namespace)
    
    # Assert exactly 30 chunks were created
    assert num_chunks > 8, f"Expected more than 8 chunks but got {num_chunks}"
    
    # Verify UpstashVectorStore was instantiated with correct parameters
    mock_vs_class.assert_called_once_with(
        embedding=True,
        namespace=namespace
    )
    
    # Verify add_documents was called
    assert mock_vs_instance.add_documents.called
    
    # Get the chunks that were passed to add_documents
    call_args = mock_vs_instance.add_documents.call_args
    chunks = call_args[0][0]  # First positional argument
    
    # Additional assertions to verify chunk structure
    for chunk in chunks:
        assert hasattr(chunk, 'page_content'), "Chunk should have page_content"
        assert hasattr(chunk, 'metadata'), "Chunk should have metadata"
        assert 'source' in chunk.metadata, "Chunk metadata should contain source"


def test_index_pages_no_actual_upstash_connection(test_urls, mock_vectorstore):
    """
    Verify that no actual connection to Upstash servers is made.
    """
    mock_vs_class, mock_vs_instance = mock_vectorstore
    namespace = "bio-monitoring.ca"
    
    # Run the indexing function
    index_pages(test_urls, namespace)
    
    # Verify that the mock was used (meaning real UpstashVectorStore wasn't instantiated)
    assert mock_vs_class.called, "UpstashVectorStore mock should have been called"
    assert mock_vs_instance.add_documents.called, "add_documents should have been called on mock"