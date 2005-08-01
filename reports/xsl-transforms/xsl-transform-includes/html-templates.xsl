<?xml version="1.0"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0" xmlns="http://www.w3.org/1999/xhtml">
      <xsl:template match="Node">
        <div class="nodebox">
            <span class="notebox">Time Ran: <xsl:value-of select="Statistics/@time" /></span>
            <h2>Node: <span class="nodename"><xsl:value-of select="HostInfo/@fqdn" /></span></h2>
                <xsl:apply-templates select="Statistics" />
        </div>
    </xsl:template>
  
    <xsl:template match="Statistics">
    
        <xsl:apply-templates select="Stale" />
        <xsl:apply-templates select="Good" />
        <xsl:apply-templates select="Bad" />
        <xsl:apply-templates select="Modified" />
    </xsl:template>

    
    <xsl:template match="Good">
        <div class="clean">
            <span class="nodelisttitle">Node is clean; Everything has been satisfactorily configured.</span>
        </div>
    </xsl:template>
    
    <xsl:template match="Stale">
        <div class="warning">
            <span class="nodelisttitle">This node did not run on today's calendar date-- it may be out of date.</span>
        </div>
    </xsl:template>
    
    <xsl:template match="Bad">
        <div class="bad">
                <span class="nodelisttitle"><a href="javascript:toggleLayer('{generate-id(.)}');" title="Click to expand" class="commentLink"><xsl:value-of select="count(./*)" /></a> items did not verify and are considered Dirty.<br /></span>
                
                <div class="items" id="{generate-id(.)}"><ul class="plain">
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
                </ul></div>
            </div>
    </xsl:template>

    <xsl:template match="Modified">
        <div class="modified">
            <span class="nodelisttitle"><a href="javascript:toggleLayer('{generate-id(.)}');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(./*)" /></a> items were modified in the last run.<br /></span>
            
            <div class="items" id="{generate-id(.)}"><ul class="plain">
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
            </ul></div>
        </div>
    </xsl:template>

    <xsl:template match="ConfigFile">
        <li><b>Config File: </b>
        <tt><xsl:value-of select="@name"/></tt></li>
    </xsl:template>

    <xsl:template match="Package">
        <li><b>Package: </b>
        <tt><xsl:value-of select="@name"/></tt></li>
    </xsl:template>

    <xsl:template match="Directory">
        <li><b>Directory: </b>
        <tt><xsl:value-of select="@name"/></tt></li>
    </xsl:template>

    <xsl:template match="Service">
        <li><b>Service: </b>
        <tt><xsl:value-of select="@name"/></tt></li>
    </xsl:template>

    <xsl:template match="SymLink">
        <li><b>SymLink: </b>
        <tt><xsl:value-of select="@name"/></tt></li>
    </xsl:template>
</xsl:stylesheet>