<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0" xmlns="http://www.w3.org/1999/xhtml">
<xsl:include href="xsl-transform-includes/text-templates.xsl" />
<xsl:output method="text" indent="no" media-type="text/plain" />
<xsl:template match="Report">

<xsl:choose>
<xsl:when test="count(/Report/Node/Statistics/Bad) > 0">Subject: <xsl:value-of select="/Report/Node/@name" /> Nightly Errors
</xsl:when>
<xsl:when test="count(/Report/Node/Statistics/Good) > 0">Subject: <xsl:value-of select="/Report/Node/@name" /> Nightly Good</xsl:when>
</xsl:choose>

<xsl:if test="count(/Report/Node/Statistics/Good)+count(/Report/Node/Statistics/Bad) > 0">
<xsl:text>
</xsl:text>Report Run @ <xsl:value-of select="@time" />

</xsl:if>
<xsl:if test="count(/Report/Node/Statistics/Good) > 0">
This node configured properly.
</xsl:if>
<xsl:apply-templates select="Node">
<xsl:sort select="Statistics/@state" order="descending"/>
<xsl:sort select="@name"/>
</xsl:apply-templates>
</xsl:template></xsl:stylesheet>