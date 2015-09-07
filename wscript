#! /usr/bin/env python

# python imports
from os import environ as os_env
from os import path

# waf imports
from waflib.Configure import conf
from waflib import TaskGen
import waflib.Context as ctx

#------------------------------------------------------------------------------

TaskGen.declare_chain(
        name   = 'asciidoc-man-1',
        #rule   = '${ASCIIDOC} -b docbook -a a2x-format=manpage -d manpage -o ${TGT} ${SRC}',
        rule   = '${ASCIIDOC} -b docbook -a a2x-format=manpage -d manpage -o ${tsk.outputs[0].name} ${SRC}',
        ext_in = '.1.txt',
        ext_out = '.1',
        install_path = '${MANDIR}',
        shell = False,
        reentrant = False
        )


#------------------------------------------------------------------------------

def options(opt):
    opt.load('compiler_c')
    
    ins_gr = opt.get_option_group('Installation and uninstallation options')
    bld_gr = opt.get_option_group('Build and installation options')
    conf_gr = opt.get_option_group('Configuration options')

    def_asciidoc = 'asciidoc'
    conf_gr.add_option(
            '--asciidoc',
            dest = 'asciidoc',
            default = def_asciidoc,
            help = 'asciidoc executable. (default: %s)' % def_asciidoc
            )


    def_mandir = 'share/man'
    conf_gr.add_option(
            '--mandir',
            dest = 'mandir',
            default = def_mandir,
            help = 'Relative to PREFIX if not absoloute. Otherwise. relative to DESTDIR. (default: %s)' % def_mandir
            )

    def_disable_man = False
    conf_gr.add_option(
            '--disable-man',
            dest = 'disable_man',
            default = def_disable_man,
            action= "store_true",
            help = "Don't build manpage. (default: %s)" % def_disable_man
            )

#------------------------------------------------------------------------------

@conf
def get_conf_opts(conf):
    conf.env['DISABLE_MAN'] = conf.options.disable_man
    conf.env['ASCIIDOC'] = conf.options.asciidoc

    if conf.options.mandir[0] == '/':
        conf.env['MANDIR'] = conf.options.mandir
    else:
        conf.env['MANDIR'] = conf.env['PREFIX'] + path.sep + conf.options.mandir


@conf
def get_saldl_version(conf):

    conf.start_msg('Get saldl version from GIT')

    try:
        saldl_version = conf.cmd_and_log(['git', 'describe', '--dirty']).rstrip()
        conf.end_msg(saldl_version)
        conf.env.append_value('DEFINES', 'SALDL_VERSION="%s"' % saldl_version)
    except:
        conf.end_msg('(failed)')


@conf
def check_timer_support(conf):
    conf.check_cc(fragment=
            '''
            #include <time.h>
            int main() {
              struct timespec tp;
              clock_gettime(CLOCK_MONOTONIC_RAW, &tp);
              return 0;
            }
            ''',
            define_name="HAVE_CLOCK_MONOTONIC_RAW",
            msg = "Checking for clock_gettime() with CLOCK_MONOTONIC_RAW support",
            mandatory=False)
    conf.check_cc(function_name='gettimeofday', header_name="sys/time.h", mandatory=False)

    if not ('HAVE_CLOCK_MONOTONIC_RAW=1' in conf.env['DEFINES'] or 'HAVE_GETTIMEOFDAY=1' in conf.env['DEFINES']):
        conf.fatal('Neither clock_gettime() with CLOCK_MONOTONIC_RAW nor gettimeofday() is available!')

@conf
def check_function_mkdir(conf):
    conf.check_cc(function_name='mkdir', header_name="sys/stat.h", mandatory=False)
    conf.check_cc(function_name='_mkdir', header_name="direct.h", mandatory=False)

    if not ('HAVE_MKDIR=1' in conf.env['DEFINES'] or 'HAVE__MKDIR=1' in conf.env['DEFINES']):
        conf.fatal('Neither mkdir() nor _mkdir() is available!')

@conf
def check_warning_cflags(conf):

    print('\nChecking for warning CFLAGS support:')
    os_flags = 0

    if 'CFLAGS_SAL_WARNING' in os_env:
        warn_flags = [ os_env['CFLAGS_SAL_WARNING'] ]
        os_flags = 1
    else:
        warn_flags = [
                ['-pedantic'],
                ['-Wall'],
                ['-Wextra'],
                ['-Werror'],
                ['-Wmissing-format-attribute'],
                #['-Wno-missing-field-initializers'] # Silence stupid clang warnings
        ]

    for w in warn_flags:
        conf.check_cc(cflags = w, uselib_store='SAL_WARNING', mandatory=False)

    if conf.env['CFLAGS_SAL_WARNING']:
        conf.env.append_value('CFLAGS', conf.env['CFLAGS_SAL_WARNING'])
        print('Added warning flags: ' + str(conf.env['CFLAGS_SAL_WARNING']))
    else:
        if not os_flags:
            conf.fatal('None of the warning CFLAGS are supported by the compiler!')

@conf
def check_sanitize_cflags(conf):

    print('\nChecking for sanitize CFLAGS support:')
    os_flags = 0

    if 'CFLAGS_SAL_SANITIZE' in os_env:
        sanitizers = [ os_env['CFLAGS_SAL_SANITIZE'] ]
        os_flags = 1
    else:
        sanitizers = [
                #['-fsanitize=leak'], # Can't use this if either address or thread is enabled.
                #['-fsanitize=thread'], Does not work with new kernels
                ['-fsanitize=undefined'],
                ['-fsanitize=address'],
                ['-fsanitize-recover=all']
        ]

    for s in sanitizers:
        conf.check_cc(cflags = s, uselib_store='SAL_SANITIZE', mandatory=False)
        conf.check_cc(linkflags = s, uselib_store='SAL_SANITIZE', mandatory=False)
    
    if conf.env['CFLAGS_SAL_SANITIZE'] or conf.env['LINKFLAGS_SAL_SANITIZE']:
        if conf.env['CFLAGS_SAL_SANITIZE']:
            conf.env.append_value('CFLAGS', conf.env['CFLAGS_SAL_SANITIZE'])
            print('Added sanitizers to cflags: ' + str(conf.env['CFLAGS_SAL_SANITIZE']))
        if conf.env['LINKFLAGS_SAL_SANITIZE']:
            conf.env.append_value('LINKFLAGS', conf.env['LINKFLAGS_SAL_SANITIZE'])
            print('Added sanitizers to linkflags: ' + str(conf.env['LINKFLAGS_SAL_SANITIZE']))
    else:
            if not os_flags:
                print('None of the sanitizers are supported by the compiler!')

@conf
def check_debug_cflags(conf):

    print('\nChecking for debug CFLAGS support:')
    os_flags = 0

    if 'CFLAGS_SAL_DEBUG' in os_env:
        debug_flags = [ os_env['CFLAGS_SAL_DEBUG'] ]
        os_flags = 1
    else:
        debug_flags = [
                ['-Og'],
                ['-ggdb'],
                ['-fvar-tracking-assignments'],
                ['-fno-omit-frame-pointer'],
                ['-fstack-protector-strong']
        ]

    for d in debug_flags:
        conf.check_cc(cflags = d, uselib_store='SAL_DEBUG', mandatory=False)

    if conf.env['CFLAGS_SAL_DEBUG']:
        conf.env.append_value('CFLAGS', conf.env['CFLAGS_SAL_DEBUG'])
        print('Added debug flags: ' + str(conf.env['CFLAGS_SAL_DEBUG']))
    else:
        if not os_flags:
            conf.fatal('None of the debug CFLAGS are supported by the compiler!')

@conf
def check_link_flags(conf):

    print('\nChecking for optimized LINKFLAGS support:')
    os_flags = 0

    if 'LINKFLAGS_SAL' in os_env:
        linkflags = [ os_env['LINKFLAGS_SAL'] ]
        os_flags = 1
    else:
        linkflags = [
                ['-Wl,-O1'],
                ['-Wl,--sort-common'],
                ['-Wl,--as-needed'],
                ['-Wl,-z,relro'],
                ['-Wl,--hash-style=gnu']
        ]

    for l in linkflags:
        conf.check_cc(linkflags = l, uselib_store='SAL', mandatory=False)

    if conf.env['LINKFLAGS_SAL']:
        conf.env.append_value('LINKFLAGS', conf.env['LINKFLAGS_SAL'])
        print('Added linkflags: ' + str(conf.env['LINKFLAGS_SAL']))

@conf
def check_optimize_cflags(conf):

    print('\nChecking for optimization CFLAGS support:')
    os_flags = 0

    if 'CFLAGS_SAL_OPTIMIZE' in os_env:
        cflags = [ os_env['CFLAGS_SAL_OPTIMIZE'] ]
        os_flags = 1
    else:
        cflags = [
                ['-Ofast'],
                ['-O3 -ffast-math'],
                ['-O3'],
                ['-O2']
        ]

    for flags in cflags:
        conf.check_cc(cflags = flags, uselib_store='SAL_OPTIMIZE', mandatory=False)
        if conf.env['CFLAGS_SAL_OPTIMIZE']:
            conf.env.append_value('CFLAGS', conf.env['CFLAGS_SAL_OPTIMIZE'])
            break

    if not os_flags and not conf.env['CFLAGS_SAL_OPTIMIZE']:
        conf.fatal('None of the optimization CFLAGS are supported by the compiler!')

@conf
def check_lto_flags(conf):

    print('\nChecking for LTO CFLAGS/LINKFLAGS support:')
    c_os_flags = 0
    l_os_flags = 0

    if 'CFLAGS_SAL_LTO' in os_env:
        lto_cflags = [ os_env['CFLAGS_SAL_LTO'] ]
        c_os_flags = 1
    else:
        lto_cflags = [
                ['-flto'],
        ]

    if 'LINKFLAGS_SAL_LTO' in os_env:
        lto_linkflags = [ os_env['LINKFLAGS_SAL_LTO'] ]
        l_os_flags = 1
    else:
        lto_linkflags = [
                ['-flto']
        ]
    for c in lto_cflags:
        conf.check_cc(cflags = c, uselib_store='SAL_LTO', mandatory=False)

    for l in lto_linkflags:
        conf.check_cc(linkflags = l, uselib_store='SAL_LTO', mandatory=False)

    if conf.env['CFLAGS_SAL_LTO'] or conf.env['LINKFLAGS_SAL_LTO']:
        if conf.env['CFLAGS_SAL_LTO']:
            conf.env.append_value('CFLAGS', conf.env['CFLAGS_SAL_LTO'])
            print('Added lto flags to cflags: ' + str(conf.env['CFLAGS_SAL_LTO']))

        if conf.env['LINKFLAGS_SAL_LTO']:
            conf.env.append_value('LINKFLAGS', conf.env['LINKFLAGS_SAL_LTO'])
            print('Added lto flags to linkflags: ' + str(conf.env['LINKFLAGS_SAL_LTO']))

    else:
        if not (l_os_flags or c_os_flags):
            print('lto flags not supported by the compiler!')

@conf
def check_curl_name_headers(conf, curl_name):

    curl_includedir = conf.env['LIB' +  curl_name.upper() + '_includedir']

    if curl_includedir:

        # Check if dirname including libcurl headers is also renamed
        if path.isdir(curl_includedir + '/' + curl_name):
            # Add to INCLUDES
            conf.env.append_value('INCLUDES', curl_includedir + '/' + curl_name)
            conf.define('HAVE_CURL_INCLUDE_DIR', 1)

            # Also check if the header file is renamed
            if path.exists(curl_includedir + '/' + curl_name + '/' + curl_name + '.h'):
                # Create a header file in build/ that includes the renamed header file
                curl_include_header = conf.bldnode.make_node('curl_include.h')
                curl_include_header.write('#include <' + curl_name + '.h>\n')
                conf.define('HAVE_CURL_INCLUDE_HEADER', 1)

@conf
def check_pkg_deps(conf):

    print('\nCheck pkg-config dependencies:')

    if 'CURL_NAME' in os_env:
        curl_name = os_env['CURL_NAME']
    else:
        curl_name = 'curl'

    pkg_deps = [
            # (pkg_name, [check_args])
            #( 'lib%s' % curl_name, ['lib%s >= 7.41' % curl_name, '--cflags', '--libs'] ),
            ( 'lib%s' % curl_name, ['lib%s' % curl_name, '--cflags', '--libs'] ),
            ( 'libevent_pthreads', ['libevent_pthreads > 2.0', '--cflags', '--libs'] )
    ]

    for d in pkg_deps:

        if type(d) != tuple or len(d) != 2 or type(d[0]) != str or type(d[1]) != list :
            conf.fatal('Invalid syntax in pkg_deps.')

        pkg_name = d[0]
        check_args = d[1]

        conf.check_cfg(package = pkg_name, args = check_args)
        conf.check_cfg(package = pkg_name, variables = ['includedir', 'prefix'])

        if conf.env['INCLUDES_' + pkg_name.upper()]:
            conf.env.INCLUDES.extend(conf.env['INCLUDES_' + pkg_name.upper()])

        if conf.env[pkg_name.upper() + '_includedir']:
            conf.env.INCLUDES.extend([ conf.env[pkg_name.upper() + '_includedir'] ])

        if conf.env['LIB_' + pkg_name.upper()]:
            conf.env.LIB.extend(conf.env['LIB_' + pkg_name.upper()])

    # More things to do for custom libcurl name
    if curl_name != 'curl':
        check_curl_name_headers(conf, curl_name)

#------------------------------------------------------------------------------

def configure(conf):

    # Get opts
        get_conf_opts(conf)

    # Get version
        get_saldl_version(conf)

    # C support
        conf.load('compiler_c')


    # Defines
        conf.env.append_value('DEFINES', '_FILE_OFFSET_BITS=64')
        conf.env.append_value('DEFINES', '_GNU_SOURCE')
        conf.env.append_value('DEFINES', '_XOPEN_SOURCE=501')

    # Check availability of some functions
        check_function_mkdir(conf)
        check_timer_support(conf)
        conf.check_cc(function_name='strcasestr', header_name="string.h", mandatory=False)
        conf.check_cc(function_name='strsignal', header_name="string.h", mandatory=False)
        conf.check_cc(function_name='sigaction', header_name="signal.h", mandatory=False)
        conf.check_cc(function_name='sigaddset', header_name="signal.h", mandatory=False)

    # Required FLAGS
        # We don't use append_unique() in case the flag is overridden
        conf.env.append_value('CFLAGS', '-std=c99')
        conf.env.append_value('CFLAGS', '-fPIE') # Thread sanitizer, does not work, even with nolib
        conf.env.append_value('LINKFLAGS', '-pie')

    # Other FLAGS
        check_warning_cflags(conf)
        # TODO: add opts to choose either debug or optimize, or none
        # TODO: consider adding optional stripping if not debug
        check_debug_cflags(conf)
        #check_sanitize_cflags(conf) # core files creation takes forever
        #check_optimize_cflags(conf)

        check_link_flags(conf)
        # Note: core files are useless when lto is used
        check_lto_flags(conf)

    # Deps
        conf.env.LIB = []
        conf.env.INCLUDES = ['.']

        check_pkg_deps(conf)

        # Deps with no pkg-config support
        conf.env.append_value('LIB', 'pthread')

#------------------------------------------------------------------------------

def build(bld):

    bld.objects(
            source = [
                'progress.c',
                'events.c',
                'queue.c',
                'merge.c',
                'status.c',
                'resume.c',
                'ctrl.c',
                'common.c',
                'exit.c',
                'log.c',
                'utime.c',
                'utils.c',
                ],
            target = ['saldl-objs']
            )

    bld.program(
            use = ['saldl-objs'],
            source = ['main.c', 'saldl.c'],
            target = 'saldl'
            )

    if not bld.env['DISABLE_MAN']:
        bld(
                source = ['saldl.1.txt'],
                )

#    bld(
#            #rule = 'a2x -f manpage ${SRC} --destination-dir %s' % ctx.out_dir,
#            rule = 'asciidoc -b docbook -a a2x-format=manpage -d manpage -o ${TGT} ${SRC}',
#            source = 'saldl.1.txt',
#            target = 'share/man/saldl.1'
#            )
#    bld.install_files('${PREFIX}/share/man', ['share/man/saldl.1'])

#------------------------------------------------------------------------------
