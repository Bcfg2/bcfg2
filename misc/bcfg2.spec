%define name bcfg2
%define version 0.8.3pre1
%define release 1
%define pythonversion 2.3

Summary: Bcfg2 Client
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: BSD-like
Group: System Tools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArchitectures: noarch
Vendor: Narayan Desai <desai@mcs.anl.gov>
PreReq: lsb >= 3.0
Requires: lxml, python

%description
Bcfg2 is a configuration management tool.

%package -n bcfg2-server
Version: %{version}
Summary: Bcfg2 Server
Group: System Tools
Requires: lxml, pyOpenSSL

%description -n bcfg2-server
Bcfg2 client

%prep
%setup -q

%build
python%{pythonversion} setup.py build

%install
python%{pythonversion} setup.py install --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
mkdir -p ${RPM_BUILD_ROOT}/usr/sbin
mkdir -p ${RPM_BUILD_ROOT}/etc/init.d/
mkdir -p ${RPM_BUILD_ROOT}/etc/default
mv ${RPM_BUILD_ROOT}/usr/bin/bcfg2* ${RPM_BUILD_ROOT}/usr/sbin
mv ${RPM_BUILD_ROOT}/usr/bin/StatReports ${RPM_BUILD_ROOT}/usr/sbin
install -m 755 debian/buildsys/common/bcfg2.init ${RPM_BUILD_ROOT}/etc/init.d/bcfg2
install -m 755 debian/buildsys/common/bcfg2-server.init ${RPM_BUILD_ROOT}/etc/init.d/bcfg2-server
install -m 755 debian/bcfg2.default ${RPM_BUILD_ROOT}/etc/default/bcfg2

%clean
rm -rf $RPM_BUILD_ROOT

%files -n bcfg2-server
%defattr(-,root,root)
/usr/sbin/bcfg2-server
/usr/sbin/bcfg2-repo-validate
/usr/sbin/bcfg2-info
/usr/sbin/StatReports
/usr/bin/GenerateHostInfo
/usr/lib*/python%{pythonversion}/site-packages/Bcfg2/Server/*
/usr/share/bcfg2/schemas/*
/usr/share/bcfg2/xsl-transforms/*
/usr/share/man/man8/*
/etc/init.d/bcfg2-server

%files -n bcfg2
%defattr(-,root,root)
/usr/sbin/bcfg2
/usr/lib*/python%{pythonversion}/site-packages/Bcfg2/*.py*
/usr/lib*/python%{pythonversion}/site-packages/Bcfg2/Client/*
/usr/share/man/man1/*
/usr/share/man/man5/*
/etc/init.d/bcfg2
/etc/default/bcfg2

%post -n bcfg2-server
chkconfig --add bcfg2-server
