import os, subprocess
import png
import numpy as np 
import itertools as itertools 

workingdir = os.path.dirname(os.path.realpath(__file__))
rootdir="."
list=[]
for subdir, dirs, files in os.walk(rootdir):
    for file in files:
        #print os.path.join(subdir, file)
        filepath = subdir + os.sep + file

        if filepath.endswith(".svg"):
            list.append(filepath);
            
print('workingdir:', workingdir)            
#py2output = subprocess.check_output(['python', 'py2.py', '-i', 'test.txt'])
#print('list:', list)
outdir="PNG"
pathImageMagick=r"C:\Program Files\ImageMagick-6.9.2-Q16\\convert.exe";
pathInkscape="D:\\Inkscape-0.91-1-win64\\inkscape\\inkscape.exe";
downsample_cmd = "convert {input} -colorspace RGB -filter LanczosRadius -distort Resize 384x384 -colorspace sRGB {output}".split(' ')
crop_cmd = "convert {input} -crop 128x128+128+128 {output}".split(' ')

def path512(file_name):
    return outdir+"\\"+file_name[:-4]+"_512.png"
def path1536(file_name):
    return outdir+"\\"+file_name[:-4]+"_1536.png"
def path384(file_name):
    return outdir+"\\"+file_name[:-4]+"_384.png"
def path128(file_name):
    return outdir+"\\"+file_name[:-4]+".png"

def exportSVG(file_name):
    cmd = [pathInkscape, '--export-area=512:512:1024:1024', '--export-png='+path512(file_name), file]
    result = subprocess.check_output(cmd)
    print result

def repeat(file_name):
    r=png.Reader(path512(file_name))
    columnCount, rowCount, pngData, metaData = r.asDirect() 
    planeCount = metaData['planes'] 
    image_2d = np.vstack(itertools.imap(np.uint8, pngData)) 
    image_3d = np.reshape(image_2d, (rowCount, columnCount, planeCount))
    #for x in range(image_3d.shape[0]): 
    #    for y in range(image_3d.shape[1]):
    #        if (x == y): 
    #            image_3d[x,y,0] = 255
    #            image_3d[x,y,1] = 0
    #            image_3d[x,y,2] = 0
    top = np.concatenate([image_3d, image_3d, image_3d],axis=1)
    arr3 = np.concatenate([top,top,top],axis=0)
    rowCount, columnCount, planeCount = arr3.shape 
    pngWriter = png.Writer(columnCount, rowCount, greyscale=False, alpha=True, bitdepth=8) 
    fd = open(path1536(file_name), 'wb') 
    pngWriter.write(fd,np.reshape(arr3, (-1, columnCount*planeCount))) 
    fd.close()

def downsample(file_name):
    downsample_cmd[0] = pathImageMagick
    downsample_cmd[1] = path1536(file_name)
    downsample_cmd[-1] = path384(file_name)
    result = subprocess.check_output(downsample_cmd)
    print result

def crop(file_name):
    crop_cmd[0] = pathImageMagick
    crop_cmd[1] = path384(file_name)
    crop_cmd[-1] = path128(file_name)
    result = subprocess.check_output(crop_cmd)
    print result

for file in list:
    path, file_name = os.path.split(file)
    exportSVG(file_name)
    repeat(file_name)
    downsample(file_name)
    crop(file_name)
    os.remove( path512(file_name) )
    os.remove( path1536(file_name) )
    os.remove( path384(file_name) )
    
    

