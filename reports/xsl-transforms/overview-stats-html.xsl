<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0"
                xmlns="http://www.w3.org/1999/xhtml">
    <xsl:output method="xml" media-type="text/html" doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN" doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"/>
    <xsl:template match="Report">
        <html>
              <head>
                    <title><xsl:value-of select="@name" /></title>
                    
                    <link rel="stylesheet" type="text/css" href="web-rprt-srcs/boxypastel.css" />
                    <script type="text/javascript" src="web-rprt-srcs/main.js" />
              </head>
              <body bgcolor="#ffffff">
                    <div class="header">
                        <h1><xsl:value-of select="@name" /></h1><span class="notebox">Report Run @ <xsl:value-of select="@time" /></span>
                    </div>
                    <div class="nodebox">
                        <h2>Summary:</h2>

                        <p class="indented"><xsl:value-of select="count(/Report/Node)" /> Nodes were included in your report.</p>
                        <xsl:if test="count(/Report/Node/Statistics/Good) > 0">
                            <div class="clean">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('goodsummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(/Report/Node/Statistics/Good)" /></a> nodes are clean.<br /></span>
                                <div class="items" id="goodsummary"><ul class="plain">                                    
                                    
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="HostInfo/@fqdn"/>
                                        <xsl:if test="count(Statistics/Good) > 0">
                                            <tt><xsl:value-of select="HostInfo/@fqdn" /></tt><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>
                         
                         <xsl:if test="count(/Report/Node/Statistics/Bad) > 0">
                            <div class="bad">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('badsummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(/Report/Node/Statistics/Bad)" /></a> nodes are bad.<br /></span>
                                
                                <div class="items" id="badsummary"><ul class="plain">
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="HostInfo/@fqdn"/>
                                        <xsl:if test="count(Statistics/Bad) > 0">
                                            <tt><xsl:value-of select="HostInfo/@fqdn" /></tt><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>
                        
                        <xsl:if test="count(/Report/Node/Statistics/Modified) > 0">
                            <div class="modified">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('modifiedsummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(/Report/Node/Statistics/Modified)" /></a> nodes were modified in the last run. (includes both good and bad nodes)<br /></span>
                                
                                <div class="items" id="modifiedsummary"><ul class="plain">
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="HostInfo/@fqdn"/>
                                        <xsl:if test="count(Statistics/Modified) > 0">
                                            <tt><xsl:value-of select="HostInfo/@fqdn" /></tt><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>
                        
                        <xsl:if test="count(/Report/Node/Statistics/Stale) > 0">
                            <div class="warning">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('stalesummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(/Report/Node/Statistics/Stale)" /></a> nodes did not run this calendar day.<br /></span>
                                
                                <div class="items" id="stalesummary"><ul class="plain">
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="HostInfo/@fqdn"/>
                                        <xsl:if test="count(Statistics/Stale) > 0">
                                            <tt><xsl:value-of select="HostInfo/@fqdn" /></tt><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>
                         

                            
                            <xsl:if test="count(/Report/Node/HostInfo[@pingable='N']) > 0">
                            <div class="warning">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('unpingablesummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(/Report/Node/HostInfo[@pingable='N'])" /></a> nodes were not pingable.<br /></span>
                                
                                <div class="items" id="unpingablesummary"><ul class="plain">
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="HostInfo/@fqdn"/>
                                        <xsl:if test="count(HostInfo[@pingable='N']) > 0">
                                            <tt><xsl:value-of select="HostInfo/@fqdn" /></tt><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>

                         
                         
                </div>
                <br/>
                <br/>
                <p>
                    <a href="http://validator.w3.org/check?uri=referer"><img
                      src="http://www.w3.org/Icons/valid-xhtml10"
                     alt="Valid XHTML 1.0!" height="31" width="88" /></a>
                </p>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>