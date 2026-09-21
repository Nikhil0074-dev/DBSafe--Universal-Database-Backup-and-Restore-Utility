def register_blueprints(app):
    from .auth_routes import bp as auth_bp
    from .backup_routes import bp as backup_bp
    from .database_routes import bp as database_bp
    from .log_routes import bp as log_bp
    from .page_routes import bp as page_bp
    from .restore_routes import bp as restore_bp
    from .schedule_routes import bp as schedule_bp
    from .storage_routes import bp as storage_bp

    for blueprint in (page_bp, auth_bp, database_bp, backup_bp, restore_bp,
                      schedule_bp, storage_bp, log_bp):
        app.register_blueprint(blueprint)
