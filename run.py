from dotenv import load_dotenv
from app import create_app
from app.config import Config

load_dotenv()
flask_app = create_app()
application = flask_app

if __name__ == "__main__":
    flask_app.run(
        host='127.0.0.1',
        port=Config.FLASK_PORT,
        debug=Config.DEBUG
    )