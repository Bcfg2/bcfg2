<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0" xmlns="http://www.w3.org/1999/xhtml">
<xsl:template match="Node">   
<xsl:if test="count(Statistics/Good)+count(Statistics/Bad)+count(Statistics/Stale)+count(Statistics/Modified) > 0">

<xsl:text>

    </xsl:text>Node:<xsl:value-of select="HostInfo/@fqdn" /><xsl:text>
        </xsl:text>Time Ran: <xsl:value-of select="Statistics/@time" />.
<xsl:apply-templates select="Statistics" />
	</xsl:if>
</xsl:template>
  
<xsl:template match="Statistics">
        <xsl:apply-templates select="Stale" />
        <xsl:apply-templates select="Good" />
        <xsl:apply-templates select="Bad" />
        <xsl:apply-templates select="Modified" />
</xsl:template>
<xsl:template match="Good">
<xsl:text>        </xsl:text>Node is clean; Everything has been satisfactorily configured.
</xsl:template>
<xsl:template match="Stale">
<xsl:text>        </xsl:text>This node did not run today-- it may be out of date.
</xsl:template>
<xsl:template match="Bad">
<xsl:text>        </xsl:text><xsl:value-of select="count(./*)" /> items did not verify and are considered Dirty:
        <xsl:apply-templates select="ConfigFile">
           <xsl:sort select="@name"/>
        </xsl:apply-templates>
        <xsl:apply-templates select="Directory">
           <xsl:sort select="@name"/>
        </xsl:apply-templates>
        <xsl:apply-templates select="Package">
           <xsl:sort select="@name"/>
        </xsl:apply-templates>
        <xsl:apply-templates select="Service">
           <xsl:sort select="@name"/>
        </xsl:apply-templates>
        <xsl:apply-templates select="SymLink">
           <xsl:sort select="@name"/>
        </xsl:apply-templates>
    </xsl:template>

<xsl:template match="Modified">
<xsl:text>        </xsl:text><xsl:value-of select="count(./*)" /> items were modified in the last run.
    <xsl:apply-templates select="ConfigFile">
       <xsl:sort select="@name"/>
    </xsl:apply-templates>
    <xsl:apply-templates select="Directory">
       <xsl:sort select="@name"/>
    </xsl:apply-templates>
    <xsl:apply-templates select="Package">
       <xsl:sort select="@name"/>
    </xsl:apply-templates>
    <xsl:apply-templates select="Service">
       <xsl:sort select="@name"/>
    </xsl:apply-templates>
    <xsl:apply-templates select="SymLink">
       <xsl:sort select="@name"/>
    </xsl:apply-templates>
</xsl:template>

<xsl:template match="ConfigFile">
<xsl:text>
        </xsl:text>Config File: <xsl:value-of select="@name"/>
</xsl:template>

<xsl:template match="Package">
<xsl:text>
        </xsl:text>Package: <xsl:value-of select="@name"/>
</xsl:template>

<xsl:template match="Directory">
<xsl:text>
        </xsl:text>Directory: <xsl:value-of select="@name"/>
</xsl:template>

<xsl:template match="Service">
<xsl:text>
        </xsl:text>Service: <xsl:value-of select="@name"/>
</xsl:template>

<xsl:template match="SymLink">
<xsl:text>
        </xsl:text>SymLink: <xsl:value-of select="@name"/>
</xsl:template>
</xsl:stylesheet>