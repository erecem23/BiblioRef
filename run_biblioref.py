# predecessor port: 8772
if __name__ == '__main__':
    # Spawn workers must not initialize another application or project store.
    from multiprocessing import freeze_support
    freeze_support()
    import app as app_module
    from biblioref.metadata.integration import install_cover_metadata
    from biblioref.parsing.review_export import install_parser_review_export

    install_cover_metadata(app_module)
    install_parser_review_export(app_module)
    app_module.run(port=8775, open_browser=True)
