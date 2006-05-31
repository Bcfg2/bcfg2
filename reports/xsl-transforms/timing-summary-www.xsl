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
                    <xsl:if test="count(/Report/@refresh-time) > 0">
			<META HTTP-EQUIV="Refresh" CONTENT="{@refresh-time}"/>
                    </xsl:if>
                    
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
                                <th class="sortable">Parse</th>
                                <th class="sortable">Probe</th>
                                <th class="sortable">Inventory</th>
                                <th class="sortable">Install</th>
                                <th class="sortable">Config</th>
                                <th class="sortable">Total</th>
                            </tr>                     
                            <xsl:apply-templates select="Node">
                                <xsl:sort select="Client/@name" order="ascending"/>
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
        <xsl:if test="count(Statistics/OpStamps) > 0">
            <tr>
                <td class="sortable"><xsl:value-of select="Client/@name" /></td><!--node name-->
                <td class="sortable"><xsl:value-of select="format-number(number(Statistics/OpStamps/@config_parse - Statistics/OpStamps/@config_download),'#.##')"/></td><!--parse-->
                <td class="sortable"><xsl:value-of select="format-number(number(Statistics/OpStamps/@probe_upload - Statistics/OpStamps/@start),'#.##')"/></td><!--probe download-->
                <td class="sortable"><xsl:value-of select="format-number(number(Statistics/OpStamps/@inventory - Statistics/OpStamps/@initialization),'#.##')"/></td><!--inventory-->
                <td class="sortable"><xsl:value-of select="format-number(number(Statistics/OpStamps/@install - Statistics/OpStamps/@inventory),'#.##')"/></td><!--install-->
                <td class="sortable"><xsl:value-of select="format-number(number(Statistics/OpStamps/@config_parse - Statistics/OpStamps/@probe_upload),'#.##')"/></td><!--config download & parse-->
                <td class="sortable"><xsl:value-of select="format-number(number(Statistics/OpStamps/@finished - Statistics/OpStamps/@start),'#.##')"/></td><!--Total-->
            </tr>
        </xsl:if>
    </xsl:template>
    
</xsl:stylesheet>