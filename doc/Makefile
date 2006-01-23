SOURCES = *.xml

manual.pdf: $(SOURCES)
	xsltproc --stringparam body.font.family Helvetica --stringparam fop.extensions 1 /usr/share/xml/docbook/stylesheet/nwalsh/fo/docbook.xsl manual.xml > manual.fo
	fop -fo manual.fo -pdf manual.pdf
