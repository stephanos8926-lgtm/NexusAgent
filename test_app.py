import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_data(client):
    response = client.get('/api/data')
    assert response.status_code == 200
    assert response.json == {'message': 'Data from API', 'status': 'success'}
