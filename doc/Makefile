SOURCES = *.xml

all : manual.pdf manual.html

%.fo: %.xml $(SOURCES)
	xsltproc --nonet --stringparam body.font.family Helvetica --stringparam fop.extensions 1 /usr/share/xml/docbook/stylesheet/nwalsh/fo/docbook.xsl $< > $@

%.html: %.xml $(SOURCES)
	xsltproc --nonet -o $@ /usr/share/xml/docbook/stylesheet/nwalsh/xhtml/docbook.xsl $<

%.pdf: %.fo
	fop -fo $< -pdf $@

