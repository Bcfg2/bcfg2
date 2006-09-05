SOURCES = *.xml

all : manual.pdf manual.html

%.fo: %.xml $(SOURCES)
	xsltproc --stringparam body.font.family Helvetica --stringparam fop.extensions 1 /usr/share/xml/docbook/stylesheet/nwalsh/fo/docbook.xsl $< > $@

%.html: %.xml $(SOURCES)
	xsltproc -o $@ /usr/share/xml/docbook/stylesheet/nwalsh/xhtml/docbook.xsl $<

%.pdf: %.fo
	fop -fo $< -pdf $@

