%define name bcfg2
%define version 0.8.6
%define release 1
%define __python python
%define pythonversion 2.3

Summary: Bcfg2 Client
Name: %{name}
Version: %{version}
Release: %{release}
Source0: ftp://ftp.mcs.anl.gov/pub/bcfg/%{name}-%{version}.tar.gz
License: BSD-like
Group: System Tools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArchitectures: noarch
Vendor: Narayan Desai <desai@mcs.anl.gov>
PreReq: lsb >= 3.0
Requires: lxml >= 0.9, python

%description
Bcfg2 is a configuration management tool.

%package -n bcfg2-server
Version: %{version}
Summary: Bcfg2 Server
Group: System Tools
Requires: bcfg2, pyOpenSSL
%if "%{_vendor}" == "redhat"
Requires: gamin-python
%endif


%description -n bcfg2-server
Bcfg2 client

%prep
%setup -q

%build
%{__python}%{pythonversion} setup.py build

%install
%{__python}%{pythonversion} setup.py install --root=%{buildroot} --record=INSTALLED_FILES
%{__install} -d %{buildroot}/usr/bin
%{__install} -d %{buildroot}/usr/sbin
%{__install} -d %{buildroot}/etc/init.d
%{__install} -d %{buildroot}/etc/default
%{__install} -d %{buildroot}/etc/cron.daily
%{__install} -d %{buildroot}/etc/cron.hourly
%{__install} -d %{buildroot}/usr/lib/bcfg2
%{__mv} %{buildroot}/usr/bin/bcfg2* %{buildroot}/usr/sbin
%{__install} -m 755 debian/buildsys/common/bcfg2.init %{buildroot}/etc/init.d/bcfg2
%{__install} -m 755 debian/buildsys/common/bcfg2-server.init %{buildroot}/etc/init.d/bcfg2-server
%{__install} -m 755 debian/bcfg2.default %{buildroot}/etc/default/bcfg2
%{__install} -m 755 debian/bcfg2.cron.daily %{buildroot}/etc/cron.daily/bcfg2
%{__install} -m 755 debian/bcfg2.cron.hourly %{buildroot}/etc/cron.hourly/bcfg2
%{__install} -m 755 tools/bcfg2-cron %{buildroot}/usr/lib/bcfg2/bcfg2-cron

%clean
[ "%{buildroot}" != "/" ] && %{__rm} -rf %{buildroot} || exit 2

%files -n bcfg2-server
%defattr(-,root,root)
/usr/sbin/bcfg2-*
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
%config(noreplace) /etc/default/bcfg2
/etc/cron.hourly/bcfg2
/etc/cron.daily/bcfg2
/usr/lib/bcfg2/bcfg2-cron

%post -n bcfg2-server
/sbin/chkconfig --add bcfg2-server

%changelog

* Fri Sep 15 2006 Narayan Desai <desai@mcs.anl.gov> - 0.8.4-1
- Initial log

