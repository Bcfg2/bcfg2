<?xml version="1.0"?> 
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0"
                xmlns="http://www.w3.org/1999/xhtml">
    <xsl:include href="xsl-transform-includes/html-templates.xsl" />
    <xsl:include href="xsl-transform-includes/main-js.xsl" />
        <xsl:include href="xsl-transform-includes/sorttable-js.xsl" />
    <xsl:include href="xsl-transform-includes/boxypastel-css.xsl" />    <xsl:output method="xml" media-type="text/html" doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN" doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"/>
    <xsl:template match="Report">
        <html>
              <head>
                    <title>
                        BCFG Performance Timings
                    </title>
                    
                    <xsl:copy-of select="$boxypastel-css" />
                    <xsl:copy-of select="$main-js" />
                    <xsl:copy-of select="$sorttable-js" />

              </head>
              <body bgcolor="#ffffff">
                    <div class="header">
                        <h1>
                            BCFG Performance Timings
                        </h1><span class="notebox">Report Run @ <xsl:value-of select="@time" /></span>
                    </div>
                    <br/>                     
                    <center> 
                        <table id="t1" class="sortable">
                            <tr>
                                <th class="sortable">Hostname</th>
                                <th class="sortable">Probefetch</th>
                                <th class="sortable">Parse</th>
                                <th class="sortable">Inventory</th>
                                <th class="sortable">Install</th>
                                <th class="sortable">Config</th>
                                <th class="sortable">Total</th>
                            </tr>                     
                            <xsl:apply-templates select="Node">
                                <xsl:sort select="HostInfo/@fqdn" order="ascending"/>
                                <xsl:sort select="@name"/>
                            </xsl:apply-templates>
                        </table>
                    </center>
            <br/>
            <br/>
            <p>
                <a href="http://validator.w3.org/check?uri=referer">Valid XHTML 1.0!</a>
            </p>
            </body>
        </html>
    </xsl:template>
    
    
    <xsl:template match="Node">
        <xsl:if test="count(Statistics/Times) > 0">
            <tr>
                <td class="sortable"><xsl:value-of select="HostInfo/@fqdn" /></td>
                <td class="sortable"><xsl:value-of select="format-number(Statistics/Times/@parse,'#.##')"/></td>
                <td class="sortable"><xsl:value-of select="format-number(Statistics/Times/@probefetch,'#.##')"/></td>
                <td class="sortable"><xsl:value-of select="format-number(Statistics/Times/@inventory,'#.##')"/></td>
                <td class="sortable"><xsl:value-of select="format-number(Statistics/Times/@install,'#.##')"/></td>
                <td class="sortable"><xsl:value-of select="format-number(Statistics/Times/@config,'#.##')"/></td>
                <td class="sortable"><xsl:value-of select="format-number(Statistics/Times/@total,'#.##')"/></td>
            </tr>
        </xsl:if>
    </xsl:template>
    
</xsl:stylesheet>