from fabric import task


@task
def upgrade(c):
    c.local("docker build . -t registry.gitlab.com/yamnikov-oleg/pythontalk-gatebot")
    c.local("docker push registry.gitlab.com/yamnikov-oleg/pythontalk-gatebot")

    with c.cd("pythontalk"):
        c.run("docker-compose pull gatebot")
        c.run("docker-compose up -d gatebot")
