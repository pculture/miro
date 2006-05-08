%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?python_sitearch: %define python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)")}
%define VERSION 0.8.3
%define RELEASE_CANDIDATE rc0
#define RELEASE_CANDIDATE
%define FULL_VERSION %{VERSION}%{?RELEASE_CANDIDATE:-}%{RELEASE_CANDIDATE}
%define RELEASE 1

Name:           Democracy
Version:        %{VERSION}
Release:        %{?RELEASE_CANDIDATE:0.}%{RELEASE}%{?RELEASE_CANDIDATE:.%{RELEASE_CANDIDATE}}%{?dist}
Summary:        Democracy Player

Group:          Applications/Multimedia
License:        GPL
URL:            http://www.getdemocracy.com/
Source0:        ftp://ftp.osuosl.org/pub/pculture.org/democracy/src/Democracy-%{FULL_VERSION}.tar.gz
#Patch1:         Democracy-mozilla-config.patch
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:      i386 x86_64
BuildRequires:  python-devel
BuildRequires:  xine-lib-devel libfame Pyrex
Requires:   	python-abi = %(%{__python} -c "import sys ; print sys.version[:3]")
Requires:	xine-lib gnome-python2-gtkmozembed libfame gnome-python2-gconf dbus-python

%description
Democracy Player


%prep
%setup -q -n Democracy-%{FULL_VERSION}
#%patch1


%build
cd platform/gtk-x11 && CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build


%install
rm -rf $RPM_BUILD_ROOT
cd platform/gtk-x11 && %{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT

 
%clean
rm -rf $RPM_BUILD_ROOT


# Include files and dirs below %{python_sitelib} (for noarch packages) and
# %{python_sitearch} (for arch-dependent packages) as appropriate, and mark
# *.pyo as %ghost (do not include in package).
%files
%defattr(-,root,root,-)
/usr/bin/*
/usr/share/democracy
/usr/share/pixmaps/*
/usr/share/applications/*.desktop
/usr/share/man/man1/*
%dir %{python_sitearch}/democracy
%dir %{python_sitearch}/democracy/compiled_templates
%dir %{python_sitearch}/democracy/dl_daemon
%dir %{python_sitearch}/democracy/dl_daemon/private
%dir %{python_sitearch}/democracy/frontend_implementation
%{python_sitearch}/democracy/*.so
%{python_sitearch}/democracy/*.py
%{python_sitearch}/democracy/*.pyc
%ghost %{python_sitearch}/democracy/*.pyo
%{python_sitearch}/democracy/*/*.py
%{python_sitearch}/democracy/*/*.pyc
%ghost %{python_sitearch}/democracy/*/*.pyo
%{python_sitearch}/democracy/*/*/*.py
%{python_sitearch}/democracy/*/*/*.pyc
%ghost %{python_sitearch}/democracy/*/*/*.pyo
%doc


%changelog
