<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0"
                xmlns="http://www.w3.org/1999/xhtml">
    <xsl:include href="xsl-transform-includes/main-js.xsl" />
    <xsl:include href="xsl-transform-includes/boxypastel-css.xsl" />
    <xsl:output method="xml" media-type="text/html" doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN" doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"/>
    <xsl:template match="Report">
	<xsl:variable name="cleannodes" select="/Report/Node[count(Statistics/Good)>0]"/>
	<xsl:variable name="dirtynodes" select="/Report/Node[count(Statistics/Bad)>0]"/>
	<xsl:variable name="modifiednodes" select="/Report/Node[count(Statistics/Modified)>0]"/>
	<xsl:variable name="stalenodes" select="/Report/Node[count(Statistics/Stale)>0]"/>
	<xsl:variable name="unpingablenodes" select="/Report/Node[Client/@pingable='N']"/>
	<xsl:variable name="pingablenodes" select="/Report/Node[Client/@pingable='Y']"/>

        <html>
              <head>
                    <title><xsl:value-of select="@name" /></title>
                    <xsl:if test="count(/Report/@refresh-time) > 0">
			<META HTTP-EQUIV="Refresh" CONTENT="{@refresh-time}"/>
                    </xsl:if>
                    
                    <xsl:copy-of select="$boxypastel-css" />
                    <xsl:copy-of select="$main-js" />
              </head>
              <body bgcolor="#ffffff">
                    <div class="header">
                        <h1><xsl:value-of select="@name" /></h1><span class="notebox">Report Run @ <xsl:value-of select="@time" /></span>
                    </div>
                    <div class="nodebox">
                        <h2>Summary:</h2>

                        <p class="indented"><xsl:value-of select="count(/Report/Node)" /> Nodes were included in your report.</p>
                        <xsl:if test="count($cleannodes) > 0">
                            <div class="clean">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('goodsummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(/Report/Node/Statistics/Good)" /></a> nodes are clean.<br /></span>
                                <div class="items" id="goodsummary"><ul class="plain">                                    
                                    
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="Client/@name"/>
                                        <xsl:if test="count(Statistics/Good) > 0">
                                            <tt><xsl:value-of select="Client/@name" /></tt><span class="mini-date"><xsl:value-of select="Statistics/@time" /></span><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>
                         
                         <xsl:if test="count($dirtynodes) > 0">
                            <div class="bad">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('badsummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(/Report/Node/Statistics/Bad)" /></a> nodes are bad.<br /></span>
                                
                                <div class="items" id="badsummary"><ul class="plain">
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="Client/@name"/>
                                        <xsl:if test="count(Statistics/Bad) > 0">
                                            <tt><xsl:value-of select="Client/@name" /></tt><span class="mini-date"><xsl:value-of select="Statistics/@time" /></span><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>
                        
                        <xsl:if test="count($modifiednodes) > 0">
                            <div class="modified">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('modifiedsummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(/Report/Node/Statistics/Modified)" /></a> nodes were modified in the last run. (includes both good and bad nodes)<br /></span>
                                
                                <div class="items" id="modifiedsummary"><ul class="plain">
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="Client/@name"/>
                                        <xsl:if test="count(Statistics/Modified) > 0">
                                            <tt><xsl:value-of select="Client/@name" /></tt><span class="mini-date"><xsl:value-of select="Statistics/@time" /></span><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>
                        
                        <xsl:if test="count($stalenodes[count(.|$pingablenodes)= count($pingablenodes)]) > 0">
                            <div class="warning">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('stalesummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count($stalenodes[count(.|$pingablenodes)= count($pingablenodes)])" /></a> nodes did not run within the last 24 hours but were pingable.<br /></span>
                                
                                <div class="items" id="stalesummary"><ul class="plain">
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="Client/@name"/>
                                        <xsl:if test="count(Statistics/Stale)-count(Client[@pingable='N']) > 0">
                                            <tt><xsl:value-of select="Client/@name" /></tt><span class="mini-date"><xsl:value-of select="Statistics/@time" /></span><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>
                         

                            
                            <xsl:if test="count($unpingablenodes) > 0">
                            <div class="down">
                                <span class="nodelisttitle"><a href="javascript:toggleLayer('unpingablesummary');" title="Click to Expand" class="commentLink"><xsl:value-of select="count(/Report/Node/Client[@pingable='N'])" /></a> nodes were down.<br /></span>
                                
                                <div class="items" id="unpingablesummary"><ul class="plain">
                                    <xsl:for-each select="Node">
                                        <xsl:sort select="Client/@name"/>
                                        <xsl:if test="count(Client[@pingable='N']) > 0">
                                            <tt><xsl:value-of select="Client/@name" /></tt><span class="mini-date"><xsl:value-of select="Statistics/@time" /></span><br/>
                                        </xsl:if>
                                    </xsl:for-each>
                                </ul></div>
                            </div>
                         </xsl:if>

                         
                         
                </div>
                <br/>
                <br/>
		<p>
        	    <a href="http://validator.w3.org/check?uri=referer">Valid XHTML 1.0!</a>
	        </p>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>