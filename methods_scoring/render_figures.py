"""Render source diagrams and recorded stimuli as Matplotlib PDFs."""
from pathlib import Path
import json,io
import fitz
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch
from PIL import Image

def save_pdf(fig,target):
    buffer=io.BytesIO();fig.savefig(buffer,format='pdf',dpi=300);payload=buffer.getvalue()
    if not payload.startswith(b'%PDF') or len(payload)<100:raise RuntimeError('Invalid generated PDF')
    temporary=Path(str(target)+'.tmp');temporary.write_bytes(payload);temporary.replace(target)

def replay(source,target):
    document=fitz.open(source);page=document[0];width,height=page.rect.width,page.rect.height
    fig=plt.figure(figsize=(width/72,height/72));ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,width);ax.set_ylim(height,0);ax.axis('off')
    # Shapes retain their source coordinates; text and icons use source positions.
    for shape in page.get_drawings():
        vertices=[];codes=[];previous=None
        for item in shape['items']:
            kind=item[0]
            if kind=='l':
                a,b=item[1:];a=tuple(a);b=tuple(b)
                if a!=previous:vertices.append(a);codes.append(MPath.MOVETO)
                vertices.append(b);codes.append(MPath.LINETO);previous=b
            elif kind=='c':
                a,b,c,d=[tuple(z) for z in item[1:]]
                if a!=previous:vertices.append(a);codes.append(MPath.MOVETO)
                vertices.extend([b,c,d]);codes.extend([MPath.CURVE4]*3);previous=d
            elif kind=='re':
                r=item[1];points=[(r.x0,r.y0),(r.x1,r.y0),(r.x1,r.y1),(r.x0,r.y1),(r.x0,r.y0)]
                vertices.extend(points);codes.extend([MPath.MOVETO,MPath.LINETO,MPath.LINETO,MPath.LINETO,MPath.CLOSEPOLY]);previous=None
            elif kind=='qu':
                q=item[1];points=[tuple(q.ul),tuple(q.ur),tuple(q.lr),tuple(q.ll),tuple(q.ul)]
                vertices.extend(points);codes.extend([MPath.MOVETO,MPath.LINETO,MPath.LINETO,MPath.LINETO,MPath.CLOSEPOLY]);previous=None
        if not vertices:continue
        if shape.get('closePath') and codes[-1]!=MPath.CLOSEPOLY:vertices.append(vertices[0]);codes.append(MPath.CLOSEPOLY)
        patch=PathPatch(MPath(vertices,codes),facecolor=shape.get('fill') or 'none',edgecolor=shape.get('color') or 'none',linewidth=shape.get('width',1),alpha=shape.get('fill_opacity',1),zorder=2)
        dash=shape.get('dashes') or '[] 0'
        import re
        match=re.search(r'\[([^]]*)\]\s*([\d.]+)',dash)
        if match and match[1].strip():patch.set_linestyle((float(match[2]),[float(v) for v in match[1].split()]))
        ax.add_patch(patch)
    for block in page.get_text('dict')['blocks']:
        if block['type']==1:
            im=Image.open(io.BytesIO(block['image']));r=block['bbox'];ax.imshow(im,extent=(r[0],r[2],r[3],r[1]),zorder=3,aspect='auto')
        elif block['type']==0:
            for line in block['lines']:
                for span in line['spans']:
                    font=span['font'].lower();family='DejaVu Sans Mono' if 'mono' in font or 'courier' in font else 'DejaVu Serif' if 'times' in font else 'DejaVu Sans'
                    col=span['color'];color=((col>>16&255)/255,(col>>8&255)/255,(col&255)/255)
                    ax.text(*span['origin'],span['text'],fontsize=span['size'],fontfamily=family,fontweight='bold' if 'bold' in font else 'normal',fontstyle='italic' if 'italic' in font or 'oblique' in font else 'normal',color=color,ha='left',va='baseline',zorder=4)
    save_pdf(fig,target);plt.close(fig)

def surveys(data,out):
    d=json.loads(Path(data).read_text());out=Path(out)/'survey_stats';out.mkdir(parents=True,exist_ok=True)
    colors=['#ED7D31','#FFD966','#70AD47','#C55A11']
    for key,name in [('method_surveys_by_year','survey_algorithms'),('property_surveys_by_year','survey_properties')]:
        labels=[str(k)+', '+str(v) for k,v in d[key].items()];values=list(d[key].values())
        fig,ax=plt.subplots(figsize=(3.8,3.5));wedges,_=ax.pie(values,colors=colors,startangle=90,counterclock=False,wedgeprops={'edgecolor':'white','linewidth':.8})
        for wedge,label in zip(wedges,labels):
            t=np.deg2rad((wedge.theta1+wedge.theta2)/2);ax.text(.73*np.cos(t),.73*np.sin(t),label,ha='center',va='center',fontsize=9,bbox={'facecolor':'#fff9ef','edgecolor':'#ead6bc','alpha':.95,'pad':2})
        ax.set_aspect('equal');fig.tight_layout();save_pdf(fig,out/(name+'.pdf'));plt.close(fig)
    names=d['method_names'];labels=['Feature imp.' if x=='Feature importance' else x for x in names]
    fig,ax=plt.subplots(figsize=(8.4,4.3));ax.bar(np.arange(len(names)),d['method_citation_counts'],color='tab:blue');ax.set_xticks(range(len(names)),labels,rotation=70,ha='right');ax.set_ylabel('Survey mentions');ax.set_ylim(0,30);ax.set_yticks([0,10,20,30]);fig.tight_layout();save_pdf(fig,out/'methods_distribution.pdf');plt.close(fig)

def render(inputs,out):
    out=Path(out);plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'pdf.fonttype':42})
    for source in sorted(Path(inputs).rglob('*')):
        if source.suffix.lower() not in {'.pdf','.png','.jpg','.jpeg'} or source.parent.name=='survey_stats':continue
        target=out/source.relative_to(inputs).with_suffix('.pdf');target.parent.mkdir(parents=True,exist_ok=True)
        if source.suffix=='.pdf':replay(source,target)
        else:
            im=Image.open(source).convert('RGB');fig=plt.figure(figsize=(im.width/150,im.height/150));ax=fig.add_axes([0,0,1,1]);ax.imshow(im);ax.axis('off');save_pdf(fig,target);plt.close(fig)
    surveys(Path(inputs).parent/'survey_counts.json',out)
