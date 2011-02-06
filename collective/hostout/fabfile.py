import os
import os.path
from fabric import api, contrib
from fabric.contrib.files import append
from collective.hostout.hostout import buildoutuser
from fabric.context_managers import cd
from pkg_resources import resource_filename
    

@buildoutuser
def run(*cmd):
    """Execute cmd on remote as login user """
    api.env.cwd = api.env.path
    api.run(' '.join(cmd))

def sudo(*cmd):
    """Execute cmd on remote as root user """
    api.env.cwd = api.env.path
    api.sudo(' '.join(cmd))

@buildoutuser
def put(file, target=None):
    """Upload specified files into the remote buildout folder"""
    if not target:
        target = file
    api.put(file, target)

@buildoutuser
def get(file, target=None):
    """Download the specified files from the remote buildout folder"""
    if not target:
        target = file
    with cd(api.env.path):
        api.get(file, target)

def deploy():
    "predeploy, uploadeggs, uploadbuildout, buildout and then postdeploy"
    hostout = api.env['hostout']
    hostout.predeploy()
    hostout.uploadeggs()
    hostout.uploadbuildout()
    hostout.buildout()
    hostout.postdeploy()

def predeploy():
    """Perform any initial plugin tasks. Call bootstrap if needed"""
    hostout = api.env['hostout']

    #run('export http_proxy=localhost:8123') # TODO get this from setting

    #if api.sudo("[ -e %s ]"%api.env.path, pty=True).succeeded:
    try:
        api.sudo("[ -e %s ]"%api.env.path, pty=True)
    except:
        hostout.bootstrap()
        hostout.setowners()

    with cd(api.env.path):
        for cmd in hostout.getPreCommands():
            api.sudo('sh -c "%s"'%cmd)


@buildoutuser
def uploadeggs():
    """Release developer eggs and send to host """
    
    hostout = api.env['hostout']

    #need to send package. cycledown servers, install it, run buildout, cycle up servers

    dl = hostout.getDownloadCache()
    contents = api.run('ls %s/dist' % dl).split()

    for pkg in hostout.localEggs():
        name = os.path.basename(pkg)
        if name not in contents:
            tmp = os.path.join('/tmp', name)
            api.put(pkg, tmp)
            api.run("mv -f %(tmp)s %(tgt)s && "
                "chown %(buildout)s %(tgt)s && "
                "chmod a+r %(tgt)s" % dict(
                    tmp = tmp,
                    tgt = os.path.join(dl, 'dist', name),
                    buildout=api.env.hostout.options['buildout-user'],
                    ))

@buildoutuser
def uploadbuildout():
    """Upload buildout pinned version of buildouts to host """
    hostout = api.env.hostout
    buildout = api.env['buildout-user']

    package = hostout.getHostoutPackage()
    tmp = os.path.join('/tmp', os.path.basename(package))
    tgt = os.path.join(hostout.getDownloadCache(), 'dist', os.path.basename(package))

    #api.env.warn_only = True
    if api.run("test -f %(tgt)s || echo 'None'" %locals()) == 'None' :
        api.put(package, tmp)
        api.run("mv %(tmp)s %(tgt)s" % locals() )
        #sudo('chown $(effectiveuser) %s' % tgt)


    user=hostout.options['buildout-user']
    install_dir=hostout.options['path']
    with cd(install_dir):
        api.run('tar -p -xvf %(tgt)s' % locals())
#    hostout.setowners()

@buildoutuser
def buildout():
    """ Run the buildout on the remote server """

    hostout = api.env.hostout
    hostout_file=hostout.getHostoutFile()
    with cd(api.env.path):
        api.run('bin/buildout -c %(hostout_file)s' % locals())


def postdeploy():
    """Perform any final plugin tasks """

    hostout = api.env.get('hostout')
    hostout.setowners()

    hostout_file=hostout.getHostoutFile()
    sudoparts = hostout.options.get('sudo-parts',None)
    if sudoparts:
        with cd(api.env.path):
            api.sudo('bin/buildout -c %(hostout_file)s install %(sudoparts)s' % locals())
 
    with cd(api.env.path):
        for cmd in hostout.getPostCommands():
            api.sudo('sh -c "%s"'%cmd)


def bootstrap():
    """ Install packages and users needed to get buildout running """
    hostos = api.env.get('hostos')
    version = api.env['python-version']
    major = '.'.join(version.split('.')[:2])
    majorshort = major.replace('.','')
    d = dict(major=major)

    if not hostos:
        hostos = api.env.hostout.detecthostos()
        
    cmd = getattr(api.env.hostout, 'bootstrap_users_%s'%hostos, api.env.hostout.bootstrap_users)
    cmd()
    
    
    
    #if api.run('python%(major)s --version'%d).succeeded:
    try:
        api.run('python%(major)s --version'%d)
    except:
        cmd = getattr(api.env.hostout, 'bootstrap_python_%s'%hostos, api.env.hostout.bootstrap_python)
        cmd()

    cmd = getattr(api.env.hostout, 'bootstrap_buildout_%s'%hostos, api.env.hostout.bootstrap_buildout)
    cmd()


def setowners():
    """ Ensure ownership and permissions are correct on buildout and cache """
    hostout = api.env.get('hostout')
    buildout = api.env['buildout-user']
    effective = api.env['effective-user']
    buildoutgroup = api.env['buildout-group']
    owner = buildout


    path = api.env.path
    bc = hostout.buildout_cache
    dl = hostout.getDownloadCache()
    dist = os.path.join(dl, 'dist')
    bc = hostout.getEggCache()
    var = os.path.join(path, 'var')
    
    # What we want is for
    # - login user to own the buildout and the cache.
    # - effective user to be own the var dir + able to read buildout and cache.
    
    api.sudo("find %(path)s  -maxdepth 0 ! -name var -exec chown -R %(buildout)s:%(buildoutgroup)s '{}' \; "
             " -exec chmod -R u+rw,g+r-w,o-rw '{}' \;" % locals())
    api.sudo('mkdir -p %(var)s && chown -R %(effective)s:%(buildoutgroup)s %(var)s && '
             ' chmod -R u+rw,g+wrs,o-rw %(var)s ' % locals())
#    api.sudo("chmod g+x `find %(path)s -perm -g-x` || find %(path)s -perm -g-x -exec chmod g+x '{}' \;" % locals()) #so effective can execute code
#    api.sudo("chmod g+s `find %(path)s -type d` || find %(path)s -type d -exec chmod g+s '{}' \;" % locals()) # so new files will keep same group
#    api.sudo("chmod g+s `find %(path)s -type d` || find %(path)s -type d -exec chmod g+s '{}' \;" % locals()) # so new files will keep same group
    
    for cache in [bc, dl, bc]:
        #HACK Have to deal with a shared cache. maybe need some kind of group
        api.sudo('mkdir -p %(cache)s && chown -R %(buildout)s:%(buildoutgroup)s %(cache)s && '
                 ' chmod -R u+rw,a+r %(cache)s ' % locals())

    #api.sudo('sudo -u $(effectiveuser) sh -c "export HOME=~$(effectiveuser) && cd $(install_dir) && bin/buildout -c $(hostout_file)"')

#    sudo('chmod 600 .installed.cfg')
#    sudo('find $(install_dir)  -type d -name var -exec chown -R $(effectiveuser) \{\} \;')
#    sudo('find $(install_dir)  -type d -name LC_MESSAGES -exec chown -R $(effectiveuser) \{\} \;')
#    sudo('find $(install_dir)  -name runzope -exec chown $(effectiveuser) \{\} \;')


def bootstrap_users():
    """ create users if needed """

    hostout = api.env.get('hostout')
    buildout = api.env['buildout-user']
    effective = api.env['effective-user']
    buildoutgroup = api.env['buildout-group']
    owner = buildout
    
    api.sudo('groupadd %s || echo "group exists"' % buildoutgroup)
    addopt = "--no-user-group -M -g %s" % buildoutgroup
    api.sudo('egrep ^%(owner)s: /etc/passwd || useradd %(owner)s %(addopt)s' % dict(owner=owner, addopt=addopt))
    api.sudo('egrep ^%(effective)s: /etc/passwd || useradd %(effective)s %(addopt)s' % dict(effective=effective, addopt=addopt))
    api.sudo('gpasswd -a %(owner)s %(buildoutgroup)s' % dict(owner=owner, buildoutgroup=buildoutgroup))
    api.sudo('gpasswd -a %(effective)s %(buildoutgroup)s' % dict(effective=effective, buildoutgroup=buildoutgroup))

    #Copy authorized keys to buildout user:
    key_filename, key = api.env.hostout.getIdentityKey()
    for owner in [api.env['buildout-user']]:
        api.sudo("mkdir -p ~%s/.ssh" % owner)
        api.sudo('touch ~%s/.ssh/authorized_keys' % owner)
        append(key, '~%s/.ssh/authorized_keys' % owner, use_sudo=True)
        api.sudo("chown -R %(owner)s ~%(owner)s/.ssh" % locals() )

def bootstrap_buildout():
    """ Create an initialised buildout directory """
    # bootstrap assumes that correct python is already installed
    path = api.env.path
    buildout = api.env['buildout-user']
    buildoutgroup = api.env['buildout-group']
    api.sudo('mkdir -p %(path)s' % locals())
    api.sudo('chown -R %(buildout)s:%(buildoutgroup)s %(path)s'%locals())

    buildoutcache = api.env['buildout-cache']
    api.sudo('mkdir -p %s/eggs' % buildoutcache)
    api.sudo('mkdir -p %s/downloads/dist' % buildoutcache)
    api.sudo('mkdir -p %s/extends' % buildoutcache)
    api.sudo('chown -R %s:%s %s' % (buildout, buildoutgroup, buildoutcache))
    api.env.cwd = api.env.path
   
    bootstrap = resource_filename(__name__, 'bootstrap.py')
    api.put(bootstrap, '%s/bootstrap.py' % path)
    
    # put in simplest buildout to get bootstrap to run
    api.sudo('echo "[buildout]" > buildout.cfg')

    python = api.env.get('python')
    if not python or python == 'buildout':
        
        version = api.env['python-version']
        major = '.'.join(version.split('.')[:2])
        python = "python%s" % major

    with cd(api.env.path):
        api.sudo('%s bootstrap.py --distribute' % python)


def bootstrap_python():
    version = api.env['python-version']
    major = '.'.join(version.split('.')[:2])
    majorshort = major.replace('.','')
    d = dict(major=major)
    
    
    with cd('/tmp'):
        api.run('curl http://python.org/ftp/python/%(major)s/Python-%(major)s.tgz > Python-%(major)s.tgz'%d)
        api.run('tar xzf Python-%(major)s.tgz'%d)
        with cd('Python-%(major)s'%d):
#            api.run("sed 's/#readline/readline/' Modules/Setup.dist > TMPFILE && mv TMPFILE Modules/Setup.dist")
#            api.run("sed 's/#_socket/_socket/' Modules/Setup.dist > TMPFILE && mv TMPFILE Modules/Setup.dist")
            
            api.run('./configure  --enable-unicode=ucs4 --with-threads --with-readline --with-dbm --with-zlib --with-ssl --with-bz2')
            api.run('make')
            api.sudo('make altinstall')    


def bootstrap_python_ubuntu():
    """Update ubuntu with build tools, python and bootstrap buildout"""
    hostout = api.env.get('hostout')
    path = api.env.path
     
    
    version = api.env['python-version']
    major = '.'.join(version.split('.')[:2])
    
    #Install and Update Dependencies

    #contrib.files.append(apt_source, '/etc/apt/source.list', use_sudo=True)
    api.sudo('apt-get -yq update ')
    api.sudo('apt-get -yq install '
             'build-essential '
#             'python-libxml2 '
#             'python-elementtree '
#             'python-celementtree '
             'ncurses-dev '
             'libncurses5-dev '
# needed for lxml on lucid
             'libz-dev '
             'libdb4.6 '
             'libxp-dev '
             'libreadline5 '
             'libreadline5-dev '
             'libbz2-dev '
             'libssl-dev '
             #'openssl '
             #'openssl-dev '
             )

    try:
        api.sudo('apt-get -yq install python%(major)s python%(major)s-dev '%locals())
    except:
        hostout.bootstrap_python()

    #api.sudo('apt-get -yq update; apt-get dist-upgrade')

#    api.sudo('apt-get install python2.4=2.4.6-1ubuntu3.2.9.10.1 python2.4-dbg=2.4.6-1ubuntu3.2.9.10.1 \
# python2.4-dev=2.4.6-1ubuntu3.2.9.10.1 python2.4-doc=2.4.6-1ubuntu3.2.9.10.1 \
# python2.4-minimal=2.4.6-1ubuntu3.2.9.10.1')
    #wget http://mirror.aarnet.edu.au/pub/ubuntu/archive/pool/main/p/python2.4/python2.4-minimal_2.4.6-1ubuntu3.2.9.10.1_i386.deb -O python2.4-minimal.deb
    #wget http://mirror.aarnet.edu.au/pub/ubuntu/archive/pool/main/p/python2.4/python2.4_2.4.6-1ubuntu3.2.9.10.1_i386.deb -O python2.4.deb
    #wget http://mirror.aarnet.edu.au/pub/ubuntu/archive/pool/main/p/python2.4/python2.4-dev_2.4.6-1ubuntu3.2.9.10.1_i386.deb -O python2.4-dev.deb
    #sudo dpkg -i python2.4-minimal.deb python2.4.deb python2.4-dev.deb
    #rm python2.4-minimal.deb python2.4.deb python2.4-dev.deb

    # python-profiler?
    
def bootstrap_python_redhat():
    hostout = api.env.get('hostout')
    #Install and Update Dependencies
    user = hostout.options['user']

    hostout.bootstrap_allowsudo()

    # Redhat/centos don't have Python 2.6 or 2.7 in stock yum repos, use EPEL.
    # Could also use RPMforge repo: http://dag.wieers.com/rpm/FAQ.php#B
    api.sudo("rpm -Uvh --force http://download.fedora.redhat.com/pub/epel/5/i386/epel-release-5-4.noarch.rpm")


    version = api.env['python-version']
    python_versioned = 'python' + ''.join(version.split('.')[:2])

    api.sudo('yum -y install gcc gcc-c++ ')

    api.sudo('yum -y install ' +
             python_versioned + ' ' +
             python_versioned + '-devel ' + 
             'python-setuptools '
             'libxml2-python '
             'python-elementtree '
             'ncurses-devel '
             'zlib zlib-devel '
             'readline-devel '
             'bzip2-devel '
             'openssl openssl-dev '
             )

#optional stuff
#    api.sudo('yum -y install ' +
#             'python-imaging '
#             'libjpeg-devel '
#             'freetype-devel '
#             'lynx '
#             'openssl-devel '
#             'libjpeg-devel '
#            'openssl openssl-devel '
#            'libjpeg libjpeg-devel '
#            'libpng libpng-devel '
#            'libxml2 libxml2-devel '
#            'libxslt libxslt-devel ')



def detecthostos():
    #http://wiki.linuxquestions.org/wiki/Find_out_which_linux_distribution_a_system_belongs_to
    hostos = api.run(
        "([ -e /etc/SuSE-release ] && echo SuSE) || "
                "([ -e /etc/redhat-release ] && echo redhat) || "
                "([ -e /etc/fedora-release ] && echo fedora) || "
                "(lsb_release -rd) || "
                "([ -e /etc/debian-version ] && echo ubuntu) || "
                "([ -e /etc/slackware-version ] && echo slackware)"
               )
    print "Detected Hostos = %s" % hostos
    api.env['hostos'] = hostos
    return hostos


def bootstrap_allowsudo():
    """Allow any sudo without tty"""
    hostout = api.env.get('hostout')
    user = hostout.options['user']

    try:
        api.sudo("egrep \"^\%odas\ \ ALL\=\(ALL\)\ ALL\" \"/etc/sudoers\"",pty=True)
    except:
        api.sudo("echo '%odas  ALL=(ALL) ALL' >> /etc/sudoers",pty=True)

    try:
        api.sudo("egrep \"^Defaults\:\%%%(user)s\ \!requiretty\" \"/etc/sudoers\"" % dict(user=user), pty=True)
    except:
        api.sudo("echo 'Defaults:%%%(user)s !requiretty' >> /etc/sudoers" % dict(user=user), pty=True)
    



#def initcommand(cmd):
#    if cmd in ['uploadeggs','uploadbuildout','buildout','run']:
#        api.env.user = api.env.hostout.options['buildout-user']
#    else:
#        api.env.user = api.env.hostout.options['user']
#    key_filename = api.env.get('identity-file')
#    if key_filename and os.path.exists(key_filename):
#        api.env.key_filename = key_filename


