<?xml version="1.0"?>

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

<xsl:output method="html" indent="no"/>
<xsl:variable name="main-js">

<script language="JavaScript"><xsl:comment>
function toggleLayer(whichLayer)
        {
            if (document.getElementById)
            {
                // this is the way the standards work
                var style2 = document.getElementById(whichLayer).style;
                style2.display = style2.display? "":"block";
            }
            else if (document.all)
            {
                // this is the way old msie versions work
                var style2 = document.all[whichLayer].style;
                style2.display = style2.display? "":"block";
            }
            else if (document.layers)
            {
                // this is the way nn4 works
                var style2 = document.layers[whichLayer].style;
                style2.display = style2.display? "":"block";
            }
        }
// </xsl:comment></script>
</xsl:variable>
</xsl:stylesheet>

