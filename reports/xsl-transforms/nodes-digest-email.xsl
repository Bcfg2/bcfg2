<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0" xmlns="http://www.w3.org/1999/xhtml">
<xsl:include href="xsl-transform-includes/text-templates.xsl" />
<xsl:output method="text" indent="no" media-type="text/plain" />
<xsl:template match="Report">
<xsl:choose>
<xsl:when test="count(/Report/Node/Statistics/Bad) > 0">Subject: BCFG Nightly Errors (<xsl:value-of select="@name" />)
</xsl:when>
<xsl:otherwise>Subject: BCFG Nightly Good (<xsl:value-of select="@name" />)
</xsl:otherwise>
</xsl:choose>
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
</xsl:template>
</xsl:stylesheet>