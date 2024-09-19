import os
from xlwt import easyxf
import xlwt


tittle_style = xlwt.easyxf('font: height 240, name Arial, colour_index white, bold on; align: wrap on, vert centre, horiz left;' 'pattern: pattern solid, fore_colour 0x3C')

main_tittle_style = xlwt.easyxf('font: height 240, name Arial, colour_index black, bold on; align: wrap on, vert centre, horiz left;' 'pattern: pattern solid, fore_colour ice_blue')

sub_main_tittle_style = xlwt.easyxf('font: height 240, name Arial, colour_index black, bold on; align: wrap on, vert centre, horiz left;' 'pattern: pattern solid, fore_colour tan')

tittle_style_ice_blue = xlwt.easyxf('font: height 240, name Arial, colour_index black, bold on; align: wrap on, vert centre, horiz left;' 'pattern: pattern solid, fore_colour ice_blue')

subTitle_style = xlwt.easyxf('font: height 200, name Arial, colour_index white, bold on, italic on; align: wrap on, vert centre, horiz centre;' 'pattern: pattern solid, fore_colour 0x3C')

g_style = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz left;' 'pattern: pattern solid, fore_colour 0x1B')

gn_style = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1B')

gtn_style = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1B')

gm_style = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1B')

style1_even = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz left;' 'pattern: pattern solid, fore_colour 0x1A')
style1_odd = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz left;')

normal_style_left = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert bottom, horiz left;')
normal_style_right = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert bottom, horiz right;')

normal_style_left_ice_blue = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert bottom, horiz left;' 'pattern: pattern solid, fore_colour ice_blue')
normal_style_right_ice_blue = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert bottom, horiz right;' 'pattern: pattern solid, fore_colour ice_blue')
normal_style_right_ice_blue_num = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert bottom, horiz right;' 'pattern: pattern solid, fore_colour ice_blue')

style2_even = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style2_odd = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz right;')

style3_even = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz centre;' 'pattern: pattern solid, fore_colour 0x1A')
style3_odd = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz centre;')

style4_even = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style4_odd = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz right;')

style5_even = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style5_odd = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;')


style6_even = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style6_odd = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;')

style7_even = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style7_odd = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;')

style8_even = xlwt.easyxf('font: bold off,height 200,color red;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style8_odd = xlwt.easyxf('font: bold off,height 200,color red;' 'align: wrap on, vert centre, horiz right;')

style9_even = xlwt.easyxf('font: bold off,height 200,color red;' 'align: wrap on, vert centre, horiz left;' 'pattern: pattern solid, fore_colour 0x1A')
style9_odd = xlwt.easyxf('font: bold off,height 200,color red;' 'align: wrap on, vert centre, horiz left;')

style10_even = xlwt.easyxf('font: bold off,height 200,color red;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style10_odd = xlwt.easyxf('font: bold off,height 200,color red;' 'align: wrap on, vert centre, horiz right;')

style11_even = xlwt.easyxf('font: bold off,height 200,color red;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style11_odd = xlwt.easyxf('font: bold off,height 200,color red;' 'align: wrap on, vert centre, horiz right;')

style12_even = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style12_odd = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz right;')

style12_title = xlwt.easyxf('font: height 200, name Arial, colour_index white, bold on, italic on; align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x3C')

style13_even = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz centre;' 'pattern: pattern solid, fore_colour 0x1A')
style13_odd = xlwt.easyxf('font: bold off,height 200;' 'align: wrap on, vert centre, horiz centre;')

style14_even = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz left;' 'pattern: pattern solid, fore_colour 0x1A')
style14_odd = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz left;')

style15_even = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;' 'pattern: pattern solid, fore_colour 0x1A')
style15_odd = xlwt.easyxf('font: bold on,height 200;' 'align: wrap on, vert centre, horiz right;')

borders = xlwt.Borders()
borders.left = xlwt.Borders.THIN
borders.right = xlwt.Borders.THIN
borders.top = xlwt.Borders.THIN
borders.bottom = xlwt.Borders.THIN

class ExcelStyles(object):
     
    def getBorders(self):
        bdr = xlwt.Borders()
        bdr.left = xlwt.Borders.THIN
        bdr.right = xlwt.Borders.THIN
        bdr.top = xlwt.Borders.THIN
        bdr.bottom = xlwt.Borders.THIN
        return bdr 

    def title(self):
        tittle_style.borders = borders
        return tittle_style
        
    def main_title(self):
        main_tittle_style.borders = borders
        return main_tittle_style
        
    def sub_main_title(self):
        sub_main_tittle_style.borders = borders
        return sub_main_tittle_style

    def title_ice_blue(self):
        tittle_style_ice_blue.borders = borders
        return tittle_style_ice_blue
    
    def subTitle(self):
        subTitle_style.borders = borders
        return subTitle_style
        
    def normal_left(self):
        normal_style_left.borders = borders
        return normal_style_left
        
    def normal_right(self):
        normal_style_right.borders = borders
        return normal_style_right
        
    def normal_left_ice_blue(self):
        normal_style_left_ice_blue.borders = borders
        return normal_style_left_ice_blue
        
    def normal_right_ice_blue(self):
        normal_style_right_ice_blue.borders = borders
        return normal_style_right_ice_blue
        
    def normal_num_right(self):
        normal_style_right.borders = borders
        normal_style_right.num_format_str = '########0.00'
        return normal_style_right
        
    def normal_num_right_3digits(self):
        normal_style_right.borders = borders
        normal_style_right.num_format_str = '########0.000'
        return normal_style_right
        
    def normal_num_right_3separator(self):
        normal_style_right.borders = borders
        normal_style_right.num_format_str = '###,###,##0.00'
        return normal_style_right
        
    def normal_right_ice_blue_num(self):
        normal_style_right_ice_blue_num.borders = borders
        normal_style_right_ice_blue_num.num_format_str = '###,###,##0.00'
        return normal_style_right_ice_blue_num
    
    def groupByTitle(self):
        g_style.borders = borders
        return g_style
    
    def groupByTotal(self):
        gn_style.borders = borders
        gn_style.num_format_str = '########0.00'
        return gn_style
        
    def groupByTotal3digits(self):
        gn_style.borders = borders
        gn_style.num_format_str = '########0.000'
        return gn_style
        
    def groupByTotal3separator(self):
        gn_style.borders = borders
        gn_style.num_format_str = '###,###,##0.00'
        return gn_style
    
    def groupByTotalNumber(self):
        gtn_style.borders = borders
        gtn_style.num_format_str = '##########0'
        return gtn_style
    
    def groupByTotalMoney(self):
        gm_style.borders = borders
        gm_style.num_format_str = '##,##,##,##0.00'
        return gm_style
    
    
    def contentText(self, dataRowNo,fontColor='',backColor=''):
        style1 = None
        if dataRowNo % 2 == 0:
            style1 = style1_even
        else:
            style1 = style1_odd
        style1.borders = borders
        return style1
        
    def contentTextBold(self, dataRowNo,fontColor='',backColor=''):
        style14 = None
        if dataRowNo % 2 == 0:
            style14 = style14_even
        else:
            style14 = style14_odd
        style14.borders = borders
        return style14
        
    def contentTextRight(self, dataRowNo,fontColor='',backColor=''):
        style12 = None
        if dataRowNo % 2 == 0:
            style12 = style12_even
        else:
            style12 = style12_odd
        style12.borders = borders
        style12.num_format_str = '########0.00'
        return style12
        
    def titleContentTextRight(self, dataRowNo,fontColor='',backColor=''):
        style12b = None
#        if dataRowNo % 2 == 0:
#            style12 = style12_even
#        else:
        style12b = style12_title
        style12b.borders = borders
        style12b.num_format_str = '########0.00'
        return style12b
        
    def contentTextRightBold(self, dataRowNo,fontColor='',backColor=''):
        style15 = None
        if dataRowNo % 2 == 0:
            style15 = style15_even
        else:
            style15 = style15_odd
        style15.borders = borders
        style15.num_format_str = '########0.00'
        return style15
        
        
    def contentTextCentre(self, dataRowNo,fontColor='',backColor=''):
        style13 = None
        if dataRowNo % 2 == 0:
            style13 = style13_even
        else:
            style13 = style13_odd
        style13.borders = borders
        return style13
        
        
    def contentMoney(self, dataRowNo):
        if dataRowNo % 2 == 0:
             style2 = style2_even
        else:
             style2 = style2_odd
        style2.borders = borders
        style2.num_format_str = '##,##,##,##0.00'
        return style2 
    
    def contentMoneyBold(self, dataRowNo):
        if dataRowNo % 2 == 0:
             style5 = style5_even
        else:
             style5 = style5_odd
        style5.borders = borders
        style5.num_format_str = '##,##,##,##0.00'
        return style5 
    
    
     
    def contentNumber(self, dataRowNo):
        if dataRowNo % 2 == 0:
             style3 = style3_even
        else:
             style3 = style3_odd
        style3.borders = borders
        style3.num_format_str = '##########0'
        return style3  
    
    def contentDecNum(self,dataRowNo):
        if dataRowNo % 2 == 0:
             style4 = style4_even
        else:
             style4 = style4_odd
        style4.borders = borders
        style4.num_format_str = '########0.00'
        return style4
    
    def contentNumberBold(self, dataRowNo):
        if dataRowNo % 2 == 0:
             style6 = style6_even
        else:
             style6 = style6_odd
        style6.borders = borders
        style6.num_format_str = '##########0'
        return style6  
    
    def contentDecNumBold(self,dataRowNo):
        if dataRowNo % 2 == 0:
             style7 = style7_even
        else:
             style7 = style7_odd
        style7.borders = borders
        style7.num_format_str = '########0.00'
        return style7
    
    def contentMoneyRed(self, dataRowNo):
        if dataRowNo % 2 == 0:
             style8 = style8_even
        else:
             style8 = style8_odd
        style8.borders = borders
        style8.num_format_str = '##,##,##,##0.00'
        return style8 

    def contentTextRed(self, dataRowNo,fontColor='',backColor=''):
        style9 = None
        if dataRowNo % 2 == 0:
            style9 = style9_even
        else:
            style9 = style9_odd
        style9.borders = borders
        return style9

    def contentNumberRed(self, dataRowNo):
        if dataRowNo % 2 == 0:
             style10 = style10_even
        else:
             style10 = style10_odd
        style10.borders = borders
        style10.num_format_str = '##########0'
        return style10

    def contentDecNumRed(self,dataRowNo):
        if dataRowNo % 2 == 0:
             style11 = style11_even
        else:
             style11 = style11_odd
        style11.borders = borders
        style11.num_format_str = '########0.00'
        return style11

