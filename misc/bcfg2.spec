%define name bcfg2
%define version 0.2
%define release 1

Summary: Bcfg2 Server
Name: %{name}-server
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: BSD-like
Group: System Tools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArchitectures: noarch
Vendor: Narayan Desai <desai@mcs.anl.gov>

%description
Bcfg2 is a configuration management tool.

%package -n bcfg2
Name: %{name}
Version: %{version}
Summary: Bcfg2 client
Group: System Tools
Requires: sslib-python

%description -n bcfg2-client
Bcfg2 client

%prep
%setup -q

%build
python setup.py build

%install
python setup.py install --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
mv ${RPM_BUILD_ROOT}/usr/bin/Bcfg2Server ${RPM_BUILD_ROOT}/usr/sbin
mv ${RPM_BUILD_ROOT}/usr/bin/ValidateBcfg2Repo ${RPM_BUILD_ROOT}/usr/sbin
mv ${RPM_BUILD_ROOT}/usr/bin/bcfg ${RPM_BUILD_ROOT}/usr/sbin
install -m 755 debian/bcfg2.init ${RPM_BUILD_ROOT}/etc/init.d/bcfg2
install -m 755 debian/bcfg2-server.init ${RPM_BUILD_ROOT}/etc/init.d/bcfg2-server

%clean
rm -rf $RPM_BUILD_ROOT

%files -n bcfg2-server
%defattr(-,root,root)
/usr/sbin/Bcfg2Server
/usr/sbin/ValidateBcfg2Repo
/usr/lib/python2.3/site-packages/Bcfg2/Server/*
/usr/share/bcfg2/schemas/*
/usr/share/man/man8/*
/etc/init.d/bcfg2-server
%config(noreplace) /etc/bcfg2.conf

%files -n bcfg2
%defattr(-,root,root)
/usr/sbin/bcfg2
/usr/lib/python2.3/site-packages/Bcfg2/__init__.py
/usr/lib/python2.3/site-packages/Bcfg2/Client/*
/usr/share/man/man1/*
/etc/init.d/bcfg2

%post -n bcfg2-server
chkconfig --add bcfg2-server
