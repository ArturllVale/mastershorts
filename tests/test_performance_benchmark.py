import pytest
import time
import json
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_video_17min():
    """Mock a 17-minute video transcript."""
    video_duration = 17 * 60
    # Simulate roughly 150 words per minute -> 2550 words
    words = []
    for i in range(2550):
        start = i * 0.4
        end = start + 0.3
        words.append({'word': f'word_{i}', 'start': start, 'end': end, 'text': f'word_{i}'})
    
    transcript = {
        'language': 'pt',
        'segments': [
            {'start': 0, 'end': video_duration, 'words': words}
        ]
    }
    return transcript, video_duration

@patch('backend.gemini_worker.genai.Client')
def test_17min_video_performance_benchmark(mock_genai, mock_video_17min):
    from backend.viral_analysis import get_viral_clips
    import backend.llm_backend as llm_backend
    
    transcript, duration = mock_video_17min
    
    # Mock LLM active locally? Let's say we use Gemini
    llm_backend.active = MagicMock(return_value=False)
    
    mock_client = MagicMock()
    mock_genai.return_value = mock_client
    
    # Mock responses
    def mock_generate_content(*args, **kwargs):
        # We need to simulate the latency and output
        # PASS 1: ScoreResponse
        prompt = kwargs.get('contents')[1] if 'contents' in kwargs and len(kwargs.get('contents')) > 1 else ''
        if 'SCORE_PROMPT_TEMPLATE' in str(prompt) or 'pontuar' in str(prompt).lower():
            # mock pass 1
            response = MagicMock()
            # 3 windows
            response.text = json.dumps({
                "windows": [
                    {"id": f"win_{i}", "score": 90 - i} for i in range(10)
                ]
            })
            return response
        else:
            # mock pass 2
            response = MagicMock()
            response.text = json.dumps({
                "shorts": [
                    {
                        "start": 0, "end": 45, 
                        "source_window_id": "win_0", 
                        "predicted_score": 95, 
                        "explanation": "test"
                    }
                ]
            })
            return response
            
    mock_client.models.generate_content.side_effect = mock_generate_content

    # Measure performance
    import os
    os.environ['GEMINI_API_KEY'] = 'test-key'
    
    start_time = time.time()
    
    with patch('backend.viral_analysis.clip_duration_bounds', return_value=(30, 60)), \
         patch('backend.viral_analysis.clip_count_targets', return_value=(3, 10)), \
         patch('backend.viral_analysis.score_batch_size', return_value=15), \
         patch('backend.viral_analysis.detail_batch_size', return_value=8):
         
         result = get_viral_clips(transcript, duration, "Test Video")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    assert result is not None
    assert 'shorts' in result
    
    # Validate it didn't take excessively long in code paths
    # (Not counting actual network wait, which is mocked, but verifying the logic doesn't loop infinitely)
    assert total_time < 5.0 
    
    print(f"Benchmark completed in {total_time:.2f}s")
    print(f"Total LLM calls mocked: {mock_client.models.generate_content.call_count}")
