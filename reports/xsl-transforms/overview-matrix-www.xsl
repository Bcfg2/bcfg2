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
                        BCFG Overview Matrix
                    </title>
                    
                    <xsl:copy-of select="$boxypastel-css" />
                    <xsl:copy-of select="$main-js" />
                    <xsl:copy-of select="$sorttable-js" />

              </head>
              <body bgcolor="#ffffff">
                    <div class="header">
                        <h1>
                            BCFG Overview Matrix
                        </h1><span class="notebox">Report Run @ <xsl:value-of select="@time" /></span>
                    </div>
                    <br/>                     
                    <center> 
                        <table id="t1" class="sortable">
                            <tr>
                                <th class="sortable">Hostname</th>
                                <th class="sortable">Revision</th>
                                <th class="sortable">Correctness</th>
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
            <tr>
                <td width="43%"><h2><span class="nodename"><xsl:value-of select="Client/@name" /></span></h2></td>
                <td width="23%"><xsl:if test="Statistics/@revision &gt; -1" ><xsl:value-of select="Statistics/@revision" /></xsl:if></td>
                <td width="33%">
                <font style="font-size: 1px;">
                <xsl:value-of select="(((Statistics/@total)-(Statistics/@good)) div (Statistics/@total))*100"/>
                <xsl:text disable-output-escaping="yes">&amp;nbsp;</xsl:text>
                </font>
                <div class="statusborder">
                <div class="greenbar" style="width: {((Statistics/@good) div (Statistics/@total))*100}%;"><xsl:text disable-output-escaping="yes">&amp;nbsp;</xsl:text></div>
                <div class="redbar" style="width: {(((Statistics/@total)-(Statistics/@good)) div (Statistics/@total))*100}%;"><xsl:text disable-output-escaping="yes">&amp;nbsp;</xsl:text></div>
                </div>
                </td>
            </tr>
    </xsl:template>
    
</xsl:stylesheet>