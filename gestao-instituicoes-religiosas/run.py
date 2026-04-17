from core import create_app

# A função create_app constrói toda a nossa aplicação
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)