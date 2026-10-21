"""Render the generated Markdown report to a searchable, paginated PDF."""
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether, PageBreak
from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'report/CEG2003_Final_Report.md'
OUTPUT = ROOT / 'report/CEG2003_Final_Report.pdf'
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='ReportBody', fontName='Helvetica', fontSize=10, leading=14.5, textColor=colors.HexColor('#21384A'), spaceAfter=8, allowWidows=0, allowOrphans=0))
styles.add(ParagraphStyle(name='ReportTitle', fontName='Helvetica-Bold', fontSize=24, leading=29, textColor=colors.HexColor('#142C40'), spaceAfter=18))
styles.add(ParagraphStyle(name='ReportHeading', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.HexColor('#176B78'), spaceBefore=15, spaceAfter=8, keepWithNext=True))
styles.add(ParagraphStyle(name='TableBody', fontName='Helvetica', fontSize=8.2, leading=10.5, textColor=colors.HexColor('#21384A'), splitLongWords=True))
styles.add(ParagraphStyle(name='TableHeader', parent=styles['TableBody'], fontName='Helvetica-Bold', textColor=colors.white))
styles.add(ParagraphStyle(name='FigureCaption', parent=styles['ReportBody'], fontSize=8, leading=11, textColor=colors.HexColor('#566A7A')))


def rich(text):
    text = escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`(.+?)`', r'<font face="Courier">\1</font>', text)
    return text


def table_block(lines):
    parsed = [[v.strip() for v in line.strip().strip('|').split('|')] for line in lines]
    parsed = [r for r in parsed if not all(re.fullmatch(r'[-: ]+', v) for v in r)]
    n = len(parsed[0]); width = 174 * mm
    if n == 2: widths = [width * .64, width * .36]
    elif n == 7: widths = [width*.20] + [width*.80/6]*6
    else: widths = [width/n]*n
    cells = [[Paragraph(rich(v.replace('_',' ')), styles['TableHeader' if i==0 else 'TableBody']) for v in row] for i,row in enumerate(parsed)]
    table = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#176B78')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#EDF3F6'),colors.white]),
        ('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),6),
        ('RIGHTPADDING',(0,0),(-1,-1),6), ('TOPPADDING',(0,0),(-1,-1),7),
        ('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#BCCCD4')),
    ]))
    return table


def footer(canvas, doc):
    canvas.saveState(); canvas.setStrokeColor(colors.HexColor('#CFD9E0'))
    canvas.line(18*mm, 17*mm, 192*mm, 17*mm)
    canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#5F7180'))
    canvas.drawString(18*mm,12*mm,'CEG2003 | Confidential course data | Exploratory prototype')
    canvas.drawRightString(192*mm,12*mm,str(doc.page)); canvas.restoreState()


def main():
    lines = SOURCE.read_text(encoding='utf-8').splitlines(); story=[]; i=0
    while i < len(lines):
        line=lines[i].strip()
        if not line: i+=1; continue
        if line.startswith('|'):
            block=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                block.append(lines[i]); i+=1
            story.extend([KeepTogether([table_block(block)]),Spacer(1,9)]); continue
        if line.startswith('!['):
            match=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line)
            path=(SOURCE.parent/match.group(2)).resolve()
            with PILImage.open(path) as im: w,h=im.size
            width=174*mm; height=width*h/w
            if height>108*mm: width*=108*mm/height; height=108*mm
            story.append(KeepTogether([Image(str(path),width=width,height=height),Paragraph(rich(match.group(1)),styles['FigureCaption'])]))
            story.append(Spacer(1,8)); i+=1; continue
        if line.startswith('# '): story.append(Paragraph(rich(line[2:]),styles['ReportTitle']))
        elif line.startswith('## '):
            if line.startswith('## 5. Descriptive') or line.startswith('## Appendix:'):
                story.append(PageBreak())
            story.append(Paragraph(rich(line[3:]),styles['ReportHeading']))
        else:
            paragraph=[line]
            while i+1<len(lines) and lines[i+1].strip() and not lines[i+1].startswith(('#','|','![')) and not re.match(r'^\d+\.\s', lines[i+1]):
                i+=1; paragraph.append(lines[i].strip())
            story.append(Paragraph(rich(' '.join(paragraph)),styles['ReportBody']))
        i+=1
    doc=SimpleDocTemplate(str(OUTPUT),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=23*mm,
        title='CEG2003 Bus Captain Preventive Safety Review',author='CEG2003 project group',subject='Reproducible exploratory analysis of supplied bus alarm and incident data')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(f'PDF report created: {OUTPUT}')


if __name__ == '__main__': main()
