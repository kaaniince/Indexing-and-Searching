import tkinter as tk
import shelve
import re
from django.utils.encoding import smart_str
# smart_str: byte, int ve float gelebilecek girdileri string'e cevirmeye zorlar
import urllib.request as urllib2
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import dbm
pagelist=['https://ois.istinye.edu.tr/bilgipaketi/eobsakts/ogrenimprogrami/program_kodu/0401001/menu_id/p_38/tip/L/submenuheader/2/ln/tr/print/1']
print(os.getcwd())
folder_name = os.path.join(os.getcwd())
print(folder_name)

# Bu kelimeleri saymayacagiz:
ignorewords = set(['the', 'of', 'to', 'and', 'a', 'in', 'is', 'it'])

dbtables = {'urllist': os.path.join(folder_name, 'urllist.db'),
            'wordlocation': os.path.join(folder_name, 'wordlocation.db'),
            'link': os.path.join(folder_name, 'link.db'),
            'linkwords': os.path.join(folder_name, 'linkwords.db'),
            'pagerank': os.path.join(folder_name, 'pagerank.db')}

  
class crawler:
    ''' Bu sinif webde arama yapip aramalari veritabanina aktaracaktir.
    
        v1.0 - crawl dolduruldu
        v0.4 - addLinkRef olusturuldu
        v0.3 - isindexed olusturuldu ve addtoindex dolduruldu. 
        v0.2 - gettextonly ve separatewords fonksiyonlari dolduruldu. Boylece html sayfalarinda ilgili yazilar ayiklanabilir.
        v0.1 - init fonksiyonu guncellendi, createindextables ve close fonksiyonlari tanimlandi
    '''
    
    # Initialize the crawler with the name of database tabs
    def __init__(self, dbtables):
        ''' dbtables bir sozluk olmali:
        
            'urllist': 'urllist.db',
            'wordlocation':'wordlocation.db',
            'link':'link.db',
            'linkwords':'linkwords.db'}
        '''
        self.dbtables = dbtables
    


    # Extract the text from an HTML page (no tags)
    def gettextonly(self, soup):
        v = soup.string
        if v == None:
            c = soup.contents
            resulttext = ''
            for t in c:
                subtext = self.gettextonly(t)
                resulttext += subtext + '\n'
            return resulttext
        else:
            return v.strip()

    # Separate the words by any non-whitespace character
    def separatewords(self, text):
        splitter = re.compile('\\W+')
        return [s.lower() for s in splitter.split(text) if s != '']

    # Create the database tables
    def createindextables(self):
        # {url:outgoing_link_count}
        self.urllist = shelve.open(self.dbtables['urllist'], writeback=True, flag='c')

        #{word:{url:[loc1, loc2, ..., locN]}}
        self.wordlocation = shelve.open(self.dbtables['wordlocation'], writeback=True, flag='c')

        #{tourl:{fromUrl:None}}
        self.link = shelve.open(self.dbtables['link'], writeback=True, flag='c')

        #{word:[(urlFrom, urlTo), (urlFrom, urlTo), ..., (urlFrom, urlTo)]}
        self.linkwords = shelve.open(self.dbtables['linkwords'], writeback=True, flag='c')

    def close(self):
        if hasattr(self, 'urllist'): self.urllist.close()
        if hasattr(self, 'wordlocation'): self.wordlocation.close()
        if hasattr(self, 'link'): self.link.close()
        if hasattr(self, 'linkwords'): self.linkwords.close()

            
    # Return true if this url is already indexed
    def isindexed(self, url):
        # urllist = {url:outgoing_link_count}
        if not self.urllist.get(smart_str(url, None)):
            return False
        else:
            return True
    
    # Index an individual page
    def addtoindex(self, url, soup):
        if self.isindexed(url):
            print ('skip', url + ' already indexed')
            return False

        print ('Indexing ' + url)
        url = smart_str(url)
        # Get the individual words
        text = self.gettextonly(soup)
        words = self.separatewords(text)

        # Record each word found on this page
        for i in range(len(words)):
            word = smart_str(words[i])

            if word in ignorewords:
                continue

            self.wordlocation.setdefault(word, {})

            self.wordlocation[word].setdefault(url, [])
            self.wordlocation[word][url].append(i)

        return True
    
    # Add a link between two pages
    def addlinkref(self, urlFrom, urlTo, linkText):
        fromUrl = smart_str(urlFrom)
        toUrl = smart_str(urlTo)

        if fromUrl == toUrl: return False

        # if not self.link.get(toUrl, None):
        #     self.link[toUrl] = {}

        self.link.setdefault(toUrl, {})
        self.link[toUrl][fromUrl] = None

        words=self.separatewords(linkText)
        for word in words:
            word = smart_str(word)

            if word in ignorewords: continue

            self.linkwords.setdefault(word, [])

            self.linkwords[word].append((fromUrl, toUrl))

        return True  
    
    # Starting with a list of pages, do a breadth
    # first search to the given depth, indexing pages
    # as we go
    def crawl(self, pages, depth=2):
        for i in range(depth):
            newpages = set()
            for page in pages:
                try:
                    hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
                           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                           'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
                           'Accept-Encoding': 'none',
                           'Accept-Language': 'en-US,en;q=0.8',
                           'Connection': 'keep-alive'}
                    req = urllib2.Request(page, headers=hdr)
                    c = urllib2.urlopen(req)
                except Exception as e:
                    print ("Could not open {}, {}".format(page, e))
                    continue
                soup = BeautifulSoup(c.read(), 'html.parser')
                added = self.addtoindex(page, soup)

                if not added:
                    continue

                outgoingLinkCount = 0
                links = soup('a')
                for link in links:
                    if 'href' in link.attrs:
                        url = urljoin(page, link['href'])
                        #os.path.join()
                        if url.find("'") != -1:
                            continue
                            # The fragment identifier introduced
                            # by a hash mark (#) is the optional last
                            # part of a URL for a document. It is typically
                            # used to identify a portion of that document.
                        url = url.split('#')[0]  # remove location portion
                        if url[0:4] == 'http' and not self.isindexed(url):
                            newpages.add(url)
                        linkText = self.gettextonly(link)
                        added = self.addlinkref(page, url, linkText)
                        if added:
                            outgoingLinkCount += 1

                self.urllist[smart_str(page)] = outgoingLinkCount
            pages = newpages
class EndekslemeVeArama():
    def __init__(self,parent):
            self.parent= parent

            frame_1=tk.Frame(self.parent,relief=tk.GROOVE,border=10,width=200)
            frame_2=tk.Frame(self.parent,relief=tk.GROOVE,border=10,width=200)
            frame_3=tk.Frame(self.parent,relief=tk.GROOVE,borderwidth=0,width=200)
            frame_4=tk.Frame(self.parent,relief=tk.GROOVE,border=10,width=200)
            frame_1.pack(fill=tk.Y,expand=True)
            frame_2.pack(expand=True, fill=tk.X)
            frame_3.pack(expand=True, fill=tk.X)
            frame_4.pack(expand=True, fill=tk.X)
            self.emekleme(frame_1)
            self.aramaBolumu(frame_2)
            self.secimBolumu(frame_3)
            self.listelemeBolumu(frame_4)
            self.kontrol()
    def kontrol(self):
        for i in os.listdir(os.getcwd()):
            if i.endswith('.bak') or i.endswith('.dat') or i.endswith('.dir'):
                self.listbox_listeleme.delete(0, tk.END)
                self.listbox_listeleme.insert(0,"Arama yapabilirsiniz: Lutfen yukaridaki kutuya kelimeleri girin!")
            else:
                self.listbox_listeleme.delete(0, tk.END)
                self.listbox_listeleme.insert(0,"Arama yapabilmek için onceden indeksleme yapmalısınız.")

    def emekleme(self,frame):
            buton = tk.Button(frame,command=self.baslatmaButonu,text="Emeklemeyi Başlat",padx=50 ,pady=20)
            buton.pack( side = tk.TOP)
    def baslatmaButonu(self):
            
            crawler_ = crawler(dbtables)
            crawler_.createindextables()
            crawler_.crawl(pagelist, 2)
            crawler_.close()
            if self.listbox_listeleme.size() !=0:
                self.listbox_listeleme.delete(0, tk.END)
                self.listbox_listeleme.insert(0,"Tarama ve Endeksleme Tamamlandı!")

            else:
                self.listbox_listeleme.insert(0,"Tarama ve Endeksleme Tamamlandı!")

    def aramaBolumu(self,frame):
        self.ara =tk.StringVar()
        self.frame1 = tk.Label(frame,padx=5, pady=5,text="Arama yapılacak kelimeleri girin:")
        self.entry1 = tk.Entry(frame,textvariable=self.ara,width=100)
        self.frame1.pack( side = tk.TOP)
        self.entry1.pack( side = tk.TOP,padx=10, pady=10)
    def secimBolumu(self,frame):
        #self.frame2 = tk.Label(frame, padx=5, pady=5, text="Ayarlar", font='Helvetica 18 bold')
        #self.frame2.pack(side=tk.TOP,pady=20)
        self.secim1 = tk.IntVar()
        self.secim2 = tk.IntVar()
        self.secim3 = tk.IntVar()
        self.r1_benzerlik = tk.Checkbutton(frame, text="Kelime Frekansı", variable=self.secim1,onvalue = 1, offvalue = 0)
        self.r1_benzerlik.pack(side=tk.TOP)
        self.r2_benzerlik = tk.Checkbutton(frame, text="Inbound Link", variable=self.secim2, onvalue = 1, offvalue = 0)
        self.r2_benzerlik.pack(side=tk.TOP)
        self.r3_benzerlik = tk.Checkbutton(frame, text="PageRank", variable=self.secim3, onvalue = 1, offvalue = 0)
        self.r3_benzerlik.pack(side=tk.TOP)
        self.arabtn = tk.Button(frame,command=self.aramak,text="Ara",padx=10 ,pady=8)
        self.arabtn.pack( side = tk.TOP)
    
    def aramak(self):
        if self.ara.get()=="":
            if self.listbox_listeleme.size() !=0:
                        self.listbox_listeleme.delete(0, tk.END)      
            self.listbox_listeleme.insert(0,"Aranacak bir kelime girin!")
        else:
            try:
                if self.listbox_listeleme.size() !=0:
                        self.listbox_listeleme.delete(0, tk.END)                
                if self.secim1.get()!=1 and self.secim2.get()!=1 and self.secim3.get()!=1:
                    self.listbox_listeleme.insert(0,"Lütfen bir seçim yapın!")
                
                if self.secim3.get()==1 or self.secim2.get()==1 or self.secim1.get()==1:
                    self.mysearchengine = searcher(dbtables,self.listbox_listeleme,self.secim1.get(),self.secim2.get(),self.secim3.get())
                    self.mysearchengine.calculatepagerank()
                    self.mysearchengine.query(self.ara.get())
                    self.mysearchengine.close()
            except dbm.error:
                    self.listbox_listeleme.insert(0,"Arama yapabilmek için onceden indeksleme yapmalısınız.")

    def listelemeBolumu(self,frame):
        self.listbox_listeleme = tk.Listbox(frame,width=150,height=25)
        self.listbox_listeleme.pack(side=tk.LEFT,expand=True, fill=tk.X)

class searcher:
    def __init__(self,dbtables,listbox_listeleme,secili1,secili2,secili3):
        self.dbtables = dbtables
        self.secili1=secili1
        self.secili2=secili2

        self.secili3=secili3

        self.listbox_listeleme=listbox_listeleme
        self.opendb()

    def __del__(self):
        self.close()

    # Open the database tables
    def opendb(self):
        # {url:outgoing_link_count}
        self.urllist = shelve.open(self.dbtables['urllist'], writeback=True, flag='r')
        #{word:{url:[loc1, loc2, ..., locN]}}
        self.wordlocation = shelve.open(self.dbtables['wordlocation'], writeback=True, flag='r')
        #{tourl:{fromUrl:None}}
        self.link = shelve.open(self.dbtables['link'], writeback=True, flag='r')
        #{word:[(urlFrom, urlTo), (urlFrom, urlTo), ..., (urlFrom, urlTo)]}
        self.linkwords = shelve.open(self.dbtables['linkwords'], writeback=True, flag='r')
        #{url: rank}
        self.pagerank = shelve.open(self.dbtables['pagerank'], writeback=True, flag='c')
        
    def close(self):
        try:
            if hasattr(self, 'urllist'): self.urllist.close()
            if hasattr(self, 'wordlocation'): self.wordlocation.close()
            if hasattr(self, 'link'): self.link.close()
            if hasattr(self, 'linkwords'): self.linkwords.close()
            if hasattr(self, 'pagerank'): self.pagerank.close()
        except OSError as e:
            print("kapatirken su hatayi aldim", e)


    def getmatchingpages(self,q):
        results = {}
        # Split the words by spaces
        words = [(smart_str(word).lower()) for word in q.split()]
        if words[0] not in self.wordlocation:
                return results, words

        url_set = set(self.wordlocation[words[0]].keys())

        for word in words[1:]:
            if word not in self.wordlocation:
                return results, words
            url_set = url_set.intersection(self.wordlocation[word].keys())

        for url in url_set:
            results[url] = []
            for word in words:
                results[url].append(self.wordlocation[word][url])

        return results, words

    def getscoredlist(self, results, words):
        totalscores = dict([(url, 0) for url in results])
       # This is where you'll later put the scoring functions
        weights = []

        # word frequency scoring
        # weights = [(1.0, self.frequencyscore(results))]
        if self.secili3==1  and self.secili2!=1 and self.secili1!=1:
            weights = [(1.0, self.frequencyscore(results)),
                   (1.0, self.locationscore(results)),
                   (1.0, self.pagerankscore(results))]
        elif self.secili2==1 and self.secili1!=1 and self.secili3!=1:
            weights = [(1.0, self.frequencyscore(results)),
                        (1.0, self.locationscore(results)),

                   (1.0, self.inboundlinkscore(results))]
        elif self.secili1==1 and self.secili2!=1 and self.secili3!=1:
            weights = [(0.75, self.frequencyscore(results)),
                   (0.25, self.locationscore(results))]
        elif self.secili3==1 and self.secili1==1 and self.secili2!=1:
            weights = [(0.75, self.frequencyscore(results)),
                   (0.25, self.locationscore(results)),
                   (1.0, self.pagerankscore(results))]
        elif self.secili3==1 and self.secili2==1 and self.secili1!=1:
            weights = [(1.0, self.frequencyscore(results)),
                   (1.0, self.locationscore(results)),
                   (1.0, self.pagerankscore(results)),(1.0, self.inboundlinkscore(results))]
        elif self.secili2==1 and self.secili1==1 and self.secili3!=1:
            weights = [(0.75, self.frequencyscore(results)),
                   (0.25, self.locationscore(results)),(1.0, self.inboundlinkscore(results))]
        elif self.secili2==1 and self.secili1==1 and self.secili3==1:
            weights = [(0.75, self.frequencyscore(results)),
                   (0.25, self.locationscore(results)),(1.0, self.inboundlinkscore(results)),(1.0, self.pagerankscore(results))]
        
        for (weight,scores) in weights:
            for url in totalscores:
                totalscores[url] += weight*scores.get(url, 0)

        return totalscores

    def query(self,q):
        if self.listbox_listeleme.size() !=0:
            self.listbox_listeleme.delete(0, tk.END)
        results, words = self.getmatchingpages(q)
        if len(results) == 0:
            self.listbox_listeleme.insert(0,f"Sonuç bulunamadı!")
            return

        scores = self.getscoredlist(results,words)
        rankedscores = sorted([(score,url) for (url,score) in scores.items()],reverse=True)
     
        sayac=0
        if self.secili2==1:
            for (score,url) in rankedscores[0:10]:
                self.listbox_listeleme.insert(sayac,f"{url}")
                sayac+=1
        else:
            for (score,url) in rankedscores[0:10]:
                self.listbox_listeleme.insert(sayac,f"{score}  {self.get_linkwords_from_url(url)} --> {url}")
                sayac+=1
    def normalizescores(self,scores,smallIsBetter=0):
        vsmall = 0.00001 # Avoid division by zero errors
        if smallIsBetter:
            minscore=min(scores.values())
            minscore=max(minscore, vsmall)
            return dict([(u,float(minscore)/max(vsmall,l)) for (u,l) \
                         in scores.items()])
        else:
            maxscore = max(scores.values())
            if maxscore == 0:
                maxscore = vsmall
            return dict([(u,float(c)/maxscore) for (u,c) in scores.items()])

    def frequencyscore(self, results):
        counts = {}
        for url in results:
            score = 1
            for wordlocations in results[url]:
                score *= len(wordlocations)
            counts[url] = score
        return self.normalizescores(counts, smallIsBetter=False)

    def locationscore(self, results):
        locations=dict([(url, 1000000) for url in results])
        for url in results:
            score = 0
            for wordlocations in results[url]:
                score += min(wordlocations)
            locations[url] = score
        return self.normalizescores(locations, smallIsBetter=True)

    def worddistancescore(self, result):
        urller = result.keys()
        listoflist = result.values()
        counts = {}
        mesafe = 1000000
        if (len(listoflist)) < 2 or (len(urller)) < 2:
            for url in result:
                counts[url] = 1.0
            return counts

        for url in urller:
            for i in range(len(result[url])-1):
                for j in range(len(result[url][i])):
                    for k in range(len(result[url][i+1])):
                        if mesafe > abs(result[url][i][j]-result[url][i+1][k]):
                            mesafe = abs(result[url][i][j]-result[url][i+1][k])

            counts[url]=mesafe

        return self.normalizescores(counts, smallIsBetter=1)
    
    def inboundlinkscore(self, results):
        inboundcount=dict([(url, len(self.link[url])) for url in results if url in self.link])
        return self.normalizescores(inboundcount)

    def pagerankscore(self, results):
        self.pageranks = dict([(url, self.pagerank[url]) for url in results if url in self.pagerank])
        maxrank = max(self.pageranks.values())
        normalizedscores = dict([(url,float(score)/maxrank) for (url,score) in self.pagerank.items()])
        #return self.normalizescores(self.pageranks)
        return normalizedscores

    def calculatepagerank(self,iterations=20):
        # clear out the current page rank table
        # {url:pagerank_score}
        

        # initialize every url with a page rank of 1
        for url in self.urllist.keys():
            #print (url)
            self.pagerank[smart_str(url)] = 1.0

        for i in range(iterations):
            print ("Iteration {}".format(i))
            for url in self.urllist.keys():
                if url not in self.link.keys():
                    continue
                print (smart_str(url) , self.pagerank[smart_str(url)])
                #print (self.link[url])
                pr=0.15
                # Loop through all the pages that link to this one
                for linker in self.link[smart_str(url)]:
                    linkingpr = self.pagerank[linker]
                    #print (linker, linkingpr)


                    # Get the total number of links from the linker
                    linkingcount = self.urllist[linker]
                    #print (linkingcount)
                    pr += 0.85*(linkingpr/linkingcount)

                self.pagerank[url] = pr
    def get_linkwords_from_url(self, url):
        for self.word, self.url_tuple_listesi in self.linkwords.items():
            for url_tuples in self.url_tuple_listesi:
                if url == url_tuples[1]:
                # linkwords icindeki ikinci eleman, o linke basilarak gidilen sayfayi belirtir.Bulduysak return edebiliriz:
                    return self.word
        return 'AnaSayfa' # Eger herhangi bir url gelmediyse, kelime ana sayfada bulunmustur

root = tk.Tk()
app = EndekslemeVeArama(root)
root.mainloop()
