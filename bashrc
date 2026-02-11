# only for convenient :)

alias mm="uv run python ./manage.py migrate"
alias sp="uv run python manage.py tenant_command shell_plus --print-sql"

alias rsp="uv run python ./manage.py runserver 0.0.0.0:8000 2>&1 | tee ./logs/runserver.log"

alias guni="uv run python ./manage.py collectstatic --no-input && uv run gunicorn TiBillet.wsgi --capture-output --reload -w 3 -b 0.0.0.0:8002 2>&1 | tee ./runserver.log"

alias cel="uv run celery -A TiBillet worker -l INFO"

alias test="uv run python ./manage.py test"

alias mmes="uv run python manage.py makemessages -l en && uv run python manage.py  makemessages -l fr"
alias cmes="uv run python manage.py compilemessages"

alias pshell="eval $(uv env activate)"

tibinstall() {
    uv run python ./manage.py collectstatic
    uv run python ./manage.py migrate
    uv run python ./manage.py create_public
    echo "Création du super utilisateur :"
    uv run python ./manage.py create_tenant_superuser -s public
}

load_sql() {
    export PGPASSWORD=$POSTGRES_PASSWORD
    export PGUSER=$POSTGRES_USER
    export PGHOST=postgres
    psql --dbname $POSTGRES_DB -f $1
}