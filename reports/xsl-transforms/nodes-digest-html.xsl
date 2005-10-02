<?xml version="1.0"?> 
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0"
                xmlns="http://www.w3.org/1999/xhtml">
    <xsl:include href="xsl-transform-includes/html-templates.xsl" />
    <xsl:output method="xml" media-type="text/html" doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN" doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"/>
    <xsl:template match="Report">
        <html>
              <head>
                    <title>
                        <xsl:choose>
                            <xsl:when test="count(/Report/Node/Statistics/Bad) > 0">BCFG Nightly Errors (<xsl:value-of select="@name" />)</xsl:when>
                            <xsl:otherwise>BCFG Nightly Errors (<xsl:value-of select="@name" />)</xsl:otherwise>
                        </xsl:choose>
                    </title>
                    
                    <link rel="stylesheet" type="text/css" href="web-rprt-srcs/boxypastel.css" />
                    <script type="text/javascript" src="web-rprt-srcs/main.js" />
              </head>
              <body bgcolor="#ffffff">
                    <div class="header">
                        <h1>
                            <xsl:choose>
                                <xsl:when test="count(/Report/Node/Statistics/Bad) > 0">
                                    BCFG Nightly Errors (<xsl:value-of select="@name" />)
                                </xsl:when>
                                <xsl:otherwise>
                                    BCFG Nightly Errors (<xsl:value-of select="@name" />)
                                </xsl:otherwise>
                            </xsl:choose>
                        </h1><span class="notebox">Report Run @ <xsl:value-of select="@time" /></span>
                    </div>
                    <div class="nodebox">
                        <h2>Summary:</h2>

                        <p class="indented"><xsl:value-of select="count(/Report/Node)" /> Nodes were included in your report.</p>
                        <xsl:if test="count(/Report/Node/Statistics/Good) > 0">
                            <div class="clean">
                                <span class="nodelisttitle"><xsl:value-of select="count(/Report/Node/Statistics/Good)" /> nodes are clean.<br /></span>
                            </div>
                         </xsl:if>
                         
                         <xsl:if test="count(/Report/Node/Statistics/Bad) > 0">
                            <div class="bad">
                                <span class="nodelisttitle"><xsl:value-of select="count(/Report/Node/Statistics/Bad)" /> nodes are bad.<br /></span>
                            </div>
                         </xsl:if>

                         <xsl:if test="count(/Report/Node/Statistics/Extra) > 0">
                            <div class="extra">
                                <span class="nodelisttitle"><xsl:value-of select="count(/Report/Node/Statistics/Extra)" /> nodes have extra configuration. (includes both good and bad nodes)<br /></span>
                            </div>
                         </xsl:if>
                        
                        <xsl:if test="count(/Report/Node/Statistics/Modified) > 0">
                            <div class="modified">
                                <span class="nodelisttitle"><xsl:value-of select="count(/Report/Node/Statistics/Modified)" /> nodes were modified in the last run. (includes both good and bad nodes)<br /></span>
                            </div>
                         </xsl:if>
                        
                        <xsl:if test="count(/Report/Node/Statistics/Stale) > 0">
                            <div class="warning">
                                <span class="nodelisttitle"><xsl:value-of select="count(/Report/Node/Statistics/Stale)" /> nodes did not run this calendar day.<br /></span>
                            </div>
                         </xsl:if>
                    </div>
                    
                    <xsl:apply-templates select="Node">
                        <xsl:sort select="Statistics/@state" order="descending"/>
                        <xsl:sort select="@name"/>
                    </xsl:apply-templates>
            <br/>
            <br/>
            <p>
                <a href="http://validator.w3.org/check?uri=referer">Valid XHTML 1.0!</a>
            </p>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>