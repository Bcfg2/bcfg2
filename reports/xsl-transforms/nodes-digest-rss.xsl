<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0" >
<xsl:include href="xsl-transform-includes/text-templates.xsl" />
<xsl:output method="xml" indent="no" media-type="text/xml" omit-xml-declaration="yes"/>
<xsl:template match="Report">
<item>
<pubDate><xsl:value-of select="@time" /></pubDate>
<xsl:choose>
<xsl:when test="count(/Report/Node/Statistics/Bad) > 0"><title>Subject: BCFG Nightly Errors (<xsl:value-of select="@name" />)</title>
</xsl:when>
<xsl:otherwise><title>Subject: BCFG Nightly Good (<xsl:value-of select="@name" />)</title>
</xsl:otherwise>
</xsl:choose>
<description>&lt;pre&gt;
<xsl:text>
</xsl:text>Report Run @ <xsl:value-of select="@time" />

SUMMARY:
<xsl:text>    </xsl:text><xsl:value-of select="count(/Report/Node)" /> nodes were included in your report.<xsl:text>
</xsl:text>
<xsl:if test="count(/Report/Node)-count(/Report/Node/Statistics/Good) = 0">
<xsl:text>    </xsl:text>All machines are configured to specification.
</xsl:if><xsl:if test="count(/Report/Node/Statistics/Good) > 0">
<xsl:text>    </xsl:text><xsl:value-of select="count(/Report/Node/Statistics/Good)" /> nodes are clean.
</xsl:if>
<xsl:if test="count(/Report/Node/Statistics/Bad) > 0">
<xsl:text>    </xsl:text><xsl:value-of select="count(/Report/Node/Statistics/Bad)" /> nodes are bad.
</xsl:if>
<xsl:if test="count(/Report/Node/Statistics/Modified) > 0">
<xsl:text>    </xsl:text><xsl:value-of select="count(/Report/Node/Statistics/Modified)" /> nodes were modified in the last run. (includes both good and bad nodes)
</xsl:if>
<xsl:if test="count(/Report/Node/Statistics/Stale) > 0">
<xsl:text>    </xsl:text><xsl:value-of select="count(/Report/Node/Statistics/Stale)" /> nodes did not run this calendar day.
</xsl:if>
DETAILS:
<xsl:apply-templates select="Node">
<xsl:sort select="Statistics/@state" order="descending"/>
<xsl:sort select="@name"/>
</xsl:apply-templates>
&lt;/pre&gt;</description>
<link>http://www-unix.mcs.anl.gov/cobalt/bcfg2/index.html</link>
</item>
</xsl:template>
</xsl:stylesheet>