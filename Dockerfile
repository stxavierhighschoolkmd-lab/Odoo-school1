FROM odoo:17

USER root

RUN pip3 install psycopg2-binary

USER odoo
