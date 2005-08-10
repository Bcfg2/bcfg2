<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0" xmlns="http://www.w3.org/1999/xhtml">
<xsl:include href="xsl-transform-includes/text-templates.xsl" />
<xsl:output method="text" indent="no" media-type="text/plain" />
<xsl:template match="Report">Subject: BCFG Nightly Statistics<xsl:text>
</xsl:text>Report Run @ <xsl:value-of select="@time" />
<xsl:variable name="cleannodes" select="/Report/Node[count(Statistics/Good)>0]"/>
<xsl:variable name="dirtynodes" select="/Report/Node[count(Statistics/Bad)>0]"/>
<xsl:variable name="modifiednodes" select="/Report/Node[count(Statistics/Modified)>0]"/>
<xsl:variable name="stalenodes" select="/Report/Node[count(Statistics/Stale)>0]"/>
<xsl:variable name="unpingablenodes" select="/Report/Node[HostInfo/@pingable='N']"/>
<xsl:variable name="pingablenodes" select="/Report/Node[HostInfo/@pingable='Y']"/>

Summary:
<xsl:text>    </xsl:text><xsl:value-of select="count($cleannodes)" /> nodes are clean.
<xsl:text>    </xsl:text><xsl:value-of select="count($dirtynodes)" /> nodes are dirty.
<xsl:text>    </xsl:text><xsl:value-of select="count($modifiednodes)" /> nodes were modified in the last run. (includes both good and bad nodes)
<xsl:text>    </xsl:text><xsl:value-of select="count($stalenodes[count(.|$pingablenodes)= count($pingablenodes)])" /> nodes did not run this calendar day but were pingable.
<xsl:text>    </xsl:text><xsl:value-of select="count($unpingablenodes)" /> nodes were not pingable.
<xsl:text>    </xsl:text>----------------------------
<xsl:text>    </xsl:text><xsl:value-of select="count(/Report/Node)" /> Total<xsl:text>

</xsl:text>


<xsl:if test="count($cleannodes) > 0">
CLEAN:
<xsl:for-each select="Node">
<xsl:sort select="HostInfo/@fqdn"/>
<xsl:if test="count(Statistics/Good) > 0">
<xsl:text>    </xsl:text><xsl:value-of select="HostInfo/@fqdn" /><xsl:text>
</xsl:text>
</xsl:if>
</xsl:for-each><xsl:text>
</xsl:text>
</xsl:if>

<xsl:if test="count($dirtynodes) > 0">
DIRTY:
<xsl:for-each select="Node">
<xsl:sort select="HostInfo/@fqdn"/>
<xsl:if test="count(Statistics/Bad) > 0">
<xsl:text>    </xsl:text><xsl:value-of select="HostInfo/@fqdn" /><xsl:text>
</xsl:text>
</xsl:if>
</xsl:for-each><xsl:text>
</xsl:text>
</xsl:if>
            
<xsl:if test="count($modifiednodes) > 0">
MODIFIED:
<xsl:for-each select="Node">
<xsl:sort select="HostInfo/@fqdn"/>
<xsl:if test="count(Statistics/Modified) > 0">
<xsl:text>    </xsl:text><xsl:value-of select="HostInfo/@fqdn" /><xsl:text>
</xsl:text>
</xsl:if>
</xsl:for-each><xsl:text>
</xsl:text>

</xsl:if>
            
<xsl:if test="count($stalenodes[count(.|$pingablenodes)= count($pingablenodes)]) > 0">
STALE:
<xsl:for-each select="Node">
<xsl:sort select="HostInfo/@fqdn"/>
<xsl:if test="count(Statistics/Stale)-count(HostInfo[@pingable='N']) > 0">
<xsl:text>    </xsl:text><xsl:value-of select="HostInfo/@fqdn" /><xsl:text>
</xsl:text>
</xsl:if>
</xsl:for-each><xsl:text>
</xsl:text>

</xsl:if>

<xsl:if test="count($unpingablenodes) > 0">
UNPINGABLE:
<xsl:for-each select="Node">
<xsl:sort select="HostInfo/@fqdn"/>
<xsl:if test="count(HostInfo[@pingable='N']) > 0">
<xsl:text>    </xsl:text><xsl:value-of select="HostInfo/@fqdn" /><xsl:text>
</xsl:text>
</xsl:if>
</xsl:for-each><xsl:text>
</xsl:text>

</xsl:if>

</xsl:template>
</xsl:stylesheet>