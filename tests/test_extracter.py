from ..extracter import Extracter
from ..interview import Interview


def test_extracter():
    ex = Extracter()
    mock_interview = Interview()
    mock_interview.transcript_chunks = [{"text": "Dit is een test over Amsterdam"}]
    ex.extract(mock_interview)
    assert mock_interview.entities
