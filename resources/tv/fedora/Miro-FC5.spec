%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?python_sitearch: %define python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)")}
%define VERSION 0.9.8
%define RELEASE_CANDIDATE rc1
#define NIGHTLY 2006-07-20
#define RELEASE_CANDIDATE 2006_07_20
%define FULL_VERSION %{VERSION}%{?RELEASE_CANDIDATE:-%{RELEASE_CANDIDATE}}
#define FULL_VERSION %{NIGHTLY}
%define RELEASE 1
%define mozversion 37:1.7.12

Name:           Miro
Version:        %{VERSION}
Release:        %{?RELEASE_CANDIDATE:0.}%{RELEASE}%{?RELEASE_CANDIDATE:.%{RELEASE_CANDIDATE}}%{?dist}
Summary:        Miro Player

Group:          Applications/Multimedia
License:        GPL
URL:            http://www.getmiro.com/
Source0:        ftp://ftp.osuosl.org/pub/pculture.org/miro/src/Miro-%{FULL_VERSION}.tar.gz
#Patch1:         Miro-mozilla-config.patch
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:      i386 x86_64
BuildRequires:  python-devel
BuildRequires:  xine-lib-devel libfame Pyrex
BuildRequires:  boost-devel
BuildRequires:  mozilla-devel = %{mozversion}
Requires:   	python-abi = %(%{__python} -c "import sys ; print sys.version[:3]")
Requires:	xine-lib gnome-python2-gtkmozembed libfame gnome-python2-gconf dbus-python
Requires:       mozilla = %{mozversion}

%description
Miro Player


%prep
%setup -q -n Miro-%{FULL_VERSION}
#%patch1


%build
cd platform/gtk-x11 && CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build


%install
rm -rf $RPM_BUILD_ROOT
cd platform/gtk-x11 && %{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT

 
%clean
rm -rf $RPM_BUILD_ROOT

%post
update-desktop-database %{_datadir}/applications


# Include files and dirs below %{python_sitelib} (for noarch packages) and
# %{python_sitearch} (for arch-dependent packages) as appropriate, and mark
# *.pyo as %ghost (do not include in package).
%files
%defattr(-,root,root,-)
/usr/bin/*
%{_datadir}/miro
%{_datadir}/pixmaps/*
%{_datadir}/applications/*.desktop
%{_datadir}/man/man1/*
%{_datadir}/mime/packages/*.xml
%{_datadir}/locale/*/LC_MESSAGES/miro.mo
%dir %{python_sitearch}/miro
%dir %{python_sitearch}/miro/compiled_templates
%dir %{python_sitearch}/miro/dl_daemon
%dir %{python_sitearch}/miro/dl_daemon/private
%dir %{python_sitearch}/miro/frontend_implementation
%{python_sitearch}/miro/*.so
%{python_sitearch}/miro/*.py
%{python_sitearch}/miro/*.pyc
%ghost %{python_sitearch}/miro/*.pyo
%{python_sitearch}/miro/*/*.py
%{python_sitearch}/miro/*/*.pyc
%ghost %{python_sitearch}/miro/*/*.pyo
%{python_sitearch}/miro/*/*/*.py
%{python_sitearch}/miro/*/*/*.pyc
%ghost %{python_sitearch}/miro/*/*/*.pyo
%doc


%changelog
