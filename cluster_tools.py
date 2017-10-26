# cluster_tools holds my classes

# IMPORTS
import re
import csv
import os
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
import statistics
from scipy.stats import norm
import seaborn as sns


# class Sequence is a sequence of nucleotides
class Sequence:

    # initialize
    def __init__(self, sequence='', code='DNA'):

        # define class variables
        self.sequence = sequence
        self.code = code
        self.length = len(sequence)


# class Gene holds a gene
class Gene:

    # initialize
    def __init__(self, locus_tag='N/A', name='N/A', is_complement='N'):

        # define class variables
        self.sequence = Sequence()
        self.organism = 'Bug buggerton'
        self.accession_num = 'XX'
        self.is_complement = is_complement  # is the gene a complementary sequence?
        self.translation = Sequence(code='protein')  # expected AA sequence from gene
        self.name = name
        self.locus_tag = locus_tag
        self.seq_start = 0  # nucleotide position of start
        self.seq_end = 1  # nucleotide position of end
        self.notes = 'I am a gene! Hear me roar.'
        self.function = 'What am I expected to do? Beg?'


# class Bug holds some attributes, a sequence, and a list of genes
class Bug:

    # initialize
    def __init__(self, name='Bug', accession_num='XX'):

        # define class vars
        self.sequence = Sequence()
        self.genes = list()
        self.name = name
        self.accession_num = accession_num

    # load genes from gene file onto bug genes
    def load_genes_from_file(self, gene_file):

        # check to make sure the gene file is valid
        if not os.path.exists(gene_file):
            print(gene_file, "does not exist!")
            return

        # open the gene file and start slapping it into the bug class
        with open(gene_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:

                try:
                    this_gene = Gene(row['locus_tag'], row['gene'], row['is_complement'])
                    this_gene.seq_start, this_gene.seq_end = int(row['loc_start']), int(row['loc_end'])
                    this_gene.translation.sequence = Sequence(sequence=row['translation'], code='protein')
                    this_gene.function = row['product']

                    # add the gene to the gene list for the bug
                    self.genes.append(this_gene)
                except ValueError:
                    # May occur if the locations are invalid
                    pass
                except IndexError:
                    # May occur with an improperly formatted file
                    print("Unexpected IndexError.")
                    pass

        return


# I use requests to get data from Entrez.
try:
    import requests
except ImportError:
    print("Requests module not found. Please download requests into python directory.")
    requests = None
    quit()


# function stringify combines the elements in a list and returns a string separated by semicolons
def stringify(foo):

    my_str = ''

    for a in foo:
        my_str = my_str + a + '; '
    return my_str[:-2]  # lops off that final "; "


# function get_entrez_data takes an accession number and uses Entrez efetch to get a file from NCBI
def get_entrez_data(acc_num, entrez_file, db='nucleotide', rettype='gb', retmode='text'):

    # First check to see if the Entrez Data already exists. No need to download, then.
    if os.path.exists(entrez_file):
        print("Entrez file for", acc_num, "is already downloaded.")
        return

    print("Now downloading Entrez Data for accession number", acc_num, "...")

    # Generate the URL
    email = 'jacob.bourgeois@tufts.edu'
    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'

    url = base + "efetch.fcgi?db=" + db + \
          "&id=" + acc_num + \
          "&rettype=" + rettype + \
          "&retmode=" + retmode + \
          "&email=" + email

    # Send the URL to Entrez
    print("Requesting Data at", url)
    r = requests.get(url)
    print("Retrieved with status code", r.status_code)

    # Check the status code. If we got a 400 error, then something went wrong. Maybe an incorrect accession?
    if r.status_code == 400:
        print("Error! Status code is 400. The accession number is likely incorrect.")
        quit()

    # Turn the request into a file at entrez_path
    print("Saving data as", entrez_file, "...")

    with open(entrez_file, 'w') as f:
        for line in r.text:
            f.write(line)

    print("Saved successfully.")

    return


# function find_genes parses the entrez file and looks for coding sequences. In the standard parsemode (gb
# flat file), they are evident by lines with 'CDS' in the first spaces. This data is written to a gene file
# at the specified directory named after the accession number.
def find_genes(acc_num, entrez_file, gene_file, parse_mode='gbflat'):

    # First check to see if gene data is already processed.
    if os.path.exists(gene_file):
        print("Gene data already processed.")
        return

    # Make sure the Entrez file exists
    if not os.path.exists(entrez_file):
        print("Entrez file missing! Fetching...")
        get_entrez_data(acc_num, entrez_file)

    print("Generating gene data for accession number", acc_num, "...")

    # Begin parsing data
    print("Parsing gene data from", entrez_file, "using parse mode", parse_mode, "...")

    if parse_mode == 'gbflat':
        parse_gbflat_genes(entrez_file, gene_file)

    # Now check the gene data quickly. Sometimes, the gb file for certain accession numbers (usually the ones
    # that start with NZ_) require a gbwithparts request. In that case, redownload and recall.

    with open(gene_file, 'r') as f:

        # get the second line
        f.readline()
        line = f.readline()

        a = (line == '')

        # if a field has a blank value, no genes were added! redownload and recall function.
        if line == '':

            print("No genes detected! Redownloading database from Entrez...")

            # remove the old data
            os.remove(entrez_file)
            f.close()
            os.remove(gene_file)
            print("Old Entrez file removed.")

            get_entrez_data(acc_num, entrez_file, rettype='gbwithparts')
            find_genes(acc_num, entrez_file, gene_file)

    return


# this gene parser grabs data from gbflat files.
def parse_gbflat_genes(entrez_file, gene_file):

    # Define regex passphrases
    match_comp_loc = re.compile('(?<=complement\()[a-z-0-9. ]*', re.I)  # captures complement(.....)

    with open(entrez_file, 'r') as e:

        with open(gene_file, 'w') as g:

            # make g into a csv writer
            writer = csv.writer(g, delimiter=',')
            writer.writerow(('loc_start',
                             'loc_end',
                             'is_complement',
                             'locus_tag',
                             'gene',
                             'protein_id',
                             'product',
                             'translation'))

            end_file = -1

            # while we haven't reached the end of the file, continue scanning for data
            while end_file == -1:

                # get the next line in entrez
                data_line = e.readline()

                # if the line is empty, trip the endfile var
                if data_line == '':
                    end_file = 1

                # CDS string is within the first ten characters if a new CDS is being described.
                if 'CDS' in data_line[0:10]:

                    # blank values for row
                    gene = 'N/A'
                    locus_tag = 'N/A'
                    protein_id = 'N/A'
                    is_complement = 'N'
                    product = 'N/A'
                    translation = 'N/A'

                    try:

                        # the first line contains location data. It may be a variety of forms...

                        # May look like a complementary sequence, like complement(xxx...xxx). Regex nails this.
                        if 'complement' in data_line:
                            is_complement = 'Y'
                            try:
                                locs = match_comp_loc.findall(data_line).pop().split('..')
                                loc_start = locs[0]
                                loc_end = locs[1]
                            except IndexError:
                                loc_start = 'N/A'
                                loc_end = 'N/A'

                        # May be a join sequence, usually for pseudogenes. join(xxx.xxx, xxx.xxx).
                        elif 'join' in data_line:
                            try:
                                loc_start = data_line.split('(')[1].split(')')[0].split(',')[0].split('..')[0]
                                loc_end = data_line.split('(')[1].split(')')[0].split(',')[1].split('..')[1]
                            except IndexError:
                                loc_start = 'N/A'
                                loc_end = 'N/A'

                        # Just be the nice standard (xxx.xxx)
                        else:
                            try:
                                loc_start = (data_line.split(' ')[len(data_line.split(' ')) - 1]).split('..')[0]
                                loc_end = ((data_line.split(' ')[len(data_line.split(' ')) - 1]).split('..')[1])[:-1]
                            except IndexError:
                                loc_start = 'N/A'
                                loc_end = 'N/A'

                        # Alright, so the CDS ends when the first ten chars of the newline read 'gene'. So let's
                        # loop until we either hit the start of the new sequence or the end of the file.

                        while data_line.split('gene')[0] != '     ' and end_file == -1:

                            # get the next line
                            data_line = e.readline()

                            # check to see if the end of the file is reached
                            if data_line == '':
                                end_file = 1

                            # look for data in this line
                            if '/gene' in data_line:
                                gene = data_line.split('"')[1]

                            if 'locus_tag' in data_line:
                                locus_tag = data_line.split('"')[1]

                            if 'protein_id' in data_line:
                                protein_id = data_line.split('"')[1]

                            # alright, for product, sometimes the info spans multiple lines. So I keep looking
                            if 'product' in data_line:
                                payload = data_line.split('"')[1]

                                # if the info keeps going, there is no " at the end

                                while data_line[-2] != '"':
                                    payload = payload[:-1] + ' '
                                    data_line = e.readline()
                                    payload = payload + data_line.split('                     ')[1].split('"')[0]

                                product = payload

                            # same deal for translation.
                            if 'translation' in data_line:
                                payload = data_line.split('"')[1]

                                # if the info keeps going, there is no " at the end

                                while data_line[-2] != '"':
                                    payload = payload[:-1] + ' '
                                    data_line = e.readline()

                                    part = data_line.split('                     ')[1].split('"')[0].split('\n')[0]

                                    payload = payload + part

                                # I cannot figure out where these blank spaces come from...so split and anneal.
                                parts = payload.split(' ')
                                final_payload = ''
                                for part in parts:
                                    final_payload += part

                                translation = final_payload

                        # alright, now we have all the data for the CDS. Write the row onto the file.
                        writer.writerow((loc_start,
                                         loc_end,
                                         is_complement,
                                         locus_tag,
                                         gene,
                                         protein_id,
                                         product,
                                         translation))

                    # sometimes I get an index error due to reasons...just pass on through.
                    except IndexError:
                        pass

    print("Parsing complete! File saved as", gene_file)

    return


# function match_clusters takes cluster positions and looks for a given maximum number of genes in the
# proximity of the cluster by relying on gene data in class Bug
def match_clusters_to_genes(bug, cluster_file, results_file, trans_file, ntol=2000, max_genes=5, tlen_max=5000):

    print("Matching cluster data to genes for accession number", bug.accession_num, "...")

    # Check for cluster data
    if not os.path.exists(cluster_file):
        print("Cluster file for", bug.accession_num, "not found!! Exiting...")
        quit()

    print("Loading clustering data from", cluster_file, "...")
    # Open cluster data as csv file and add to list cluster_positions
    cluster_positions = list()
    with open(cluster_file, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            pos = int(row['genomicPos'])
            tlen = int(row['tlen'])

            # if the tlen exceeds tlen_max, ignore row
            if tlen <= tlen_max:
                cluster_positions.append(pos)

    # I prefer the clusters to be sorted :)
    cluster_positions = sorted(cluster_positions)
    num_pos = len(cluster_positions)

    print("Loaded", num_pos, "cluster locations.")

    print("Finding genes around given clusters...")

    # open the results file as a csv writer tab delim.
    with open(results_file, 'w') as f:
        writer = csv.writer(f, delimiter='\t')

        writer.writerow(("Cluster Pos", "Number Nearby Genes", "Loci", "Products"))

        # For each cluster...
        for cluster_pos in cluster_positions:

            # initialize values
            loc_start = -1
            loc_end = 1

            cluster_min = cluster_pos - ntol
            cluster_max = cluster_pos + ntol

            i = 0  # index position

            loci = list()
            products = list()
            translations = list()
            protein_id = list()

            # hit_scores list tells us the difference of distance of the middle of the gene to the cluster
            hit_scores = list()

            # while the beginning of the gene location does not exceed the cluster max position
            while loc_start <= cluster_max:

                loc_start = bug.genes[i].seq_start
                loc_end = bug.genes[i].seq_end
                loc_avg = loc_start + ((loc_end - loc_start) / 2)

                # does the end of the gene peek into the cluster range?
                if (loc_end >= cluster_min) and (loc_start <= cluster_min):
                    loci.append(bug.genes[i].locus_tag)
                    products.append(bug.genes[i].function)
                    translations.append(bug.genes[i].translation.sequence)
                    hit_scores.append(cluster_pos - loc_avg)

                # does it lie square in the middle?
                if (loc_start >= cluster_min) and (loc_end <= cluster_max):
                    loci.append(bug.genes[i].locus_tag)
                    products.append(bug.genes[i].function)
                    translations.append(bug.genes[i].translation.sequence)
                    hit_scores.append(abs(cluster_pos - loc_avg))

                # does it clip in at the end?
                if (loc_start <= cluster_max) and (loc_end >= cluster_max):
                    loci.append(bug.genes[i].locus_tag)
                    products.append(bug.genes[i].function)
                    translations.append(bug.genes[i].translation.sequence)
                    hit_scores.append(loc_avg - cluster_pos)

                i += 1

            # if there were no nearby loci, report it as such
            if len(loci) == 0:
                loci.append('No nearby loci')
                products.append('N/A')
                translations.append('N/A')

            # if the number of genes we got exceeded our threshold, trim off the edges
            if len(loci) > max_genes:

                excess = len(loci) - max_genes

                for x in range(0, excess):
                    sorted_scores = sorted(hit_scores, reverse=True)

                    # r is our element to remove based on the highest distance score
                    r = hit_scores.index(sorted_scores[0])
                    loci.pop(r)
                    products.pop(r)
                    translations.pop(r)
                    hit_scores.pop(r)

            # finally, write the row!
            writer.writerow((cluster_pos, str(len(loci)), stringify(loci), stringify(products)))

            # Oggy needs a file with all the translations, so write that shit up.
            with open(trans_file, 'a') as h:
                i = 0
                for t in translations:
                    header = '>' + bug.accession_num + '_' + loci[i] + '\n'
                    h.write(header)
                    h.write(t + '\n')
                    i += 1

    print("Linkage complete!\n")
    return


# function detect_clusters reads a data file, generates a frequency histogram of SOR reads, and detects pairs of
# cluster reads
def detect_clusters(sor_file, freq_file, cluster_file, fig_path, ctol=2000):

    # load SOR file positions and generate histogram plot as int defaultdict
    pos_freqs = defaultdict(int)
    all_pos = list()
    with open(sor_file, 'r') as f:

        reader = csv.DictReader(f)
        for row in reader:
            pos_freqs[int(row['POS'])] += 1
            all_pos.append(int(row['POS']))

    # dump a copy of the freqs onto disk for analysis
    with open(freq_file, 'w') as f:

        writer = csv.writer(f)
        writer.writerow(("Position", "Frequency"))
        for key in pos_freqs:
            writer.writerow((key, pos_freqs[key]))

    # define frequency tolerance. Maybe the median value will work?
    all_freqs = list()
    for key in pos_freqs:
        all_freqs.append(pos_freqs[key])
    ftol = statistics.median(all_freqs)
    del all_freqs

    # iterate through the histogram and detect keys that have a frequency that exceeds the tolerance
    potential_clusters = list()
    for key in pos_freqs:
        if pos_freqs[key] > ftol:
            potential_clusters.append((key, pos_freqs[key]))
    potential_clusters = sorted(potential_clusters)

    # further screen the potential clusters by taking the median of this data
    final_cluster_candidates = list()
    potential_clusters_freqs = list()
    for clusters in potential_clusters:
        potential_clusters_freqs.append(clusters[1])
    median_tol = statistics.median(potential_clusters_freqs)
    for clusters in potential_clusters:
        if clusters[1] > median_tol:
            final_cluster_candidates.append(clusters)

    # look through the filtered positions and see if neighboring clusters within ctol exist
    cluster_pos_pairs = list()
    for i in range(0, len(final_cluster_candidates)-1):

        # load cluster
        cluster_pos = final_cluster_candidates[i][0]
        next_cluster_pos = final_cluster_candidates[i+1][0]

        # look within some nucleotides at the next guy to see if he's a neighbor
        if (next_cluster_pos - cluster_pos) < ctol:

            # potential cluster pal detected!
            cluster_pos_pairs.append((cluster_pos, next_cluster_pos))

    # write these cluster pals to file for analysis
    with open(cluster_file, 'w') as f:
        writer = csv.writer(f)
        writer.writerow(("Cluster Position 1", "Cluster Position 2"))
        for pair in cluster_pos_pairs:
            writer.writerow((pair[0], pair[1]))

    # try writing a histogram!
    i = 0
    for cluster in cluster_pos_pairs:

        i += 1

        # set plot parameters
        c_start = cluster[0]
        c_end = cluster[1]

        if pos_freqs[c_start] > pos_freqs[c_end]:
            ymax = pos_freqs[c_start] + 5
        else:
            ymax = pos_freqs[c_end] + 5


        xmin = c_start - 1000
        xmax = c_end + 1000
        ymin = 0
        title = "5' clipped end frequencies between", c_start, "and", c_end
        plot_text_start = "Cluster Start:", c_start, "at frequency:", pos_freqs[c_start]
        plot_text_end = "Cluster End:", c_end, "at frequency:", pos_freqs[c_end]

        # make an array of all the histogram data to make binning work. pyplot hist automatically generates
        # the frequency data corresponding to the input array

        x = np.array(all_pos)

        plt.hist(x, bins=200, range=(xmin,xmax))
        plt.axis([xmin, xmax, ymin, ymax])
        plt.xlabel('Genomic Position')
        plt.ylabel('Frequency of Read')

        plt.annotate(plot_text_start, xy=(0.025, 0.95), xycoords='figure fraction',horizontalalignment='left',
                     verticalalignment='top', fontsize=8)
        plt.annotate(plot_text_end, xy=(0.025, 0.91), xycoords='figure fraction',horizontalalignment='left',
                     verticalalignment='top', fontsize=8)

        plt.tick_params(axis='x', labelsize=8)

        figfile = os.path.join(fig_path, str(c_start) + '_' + str(i) + '.pdf')

        plt.savefig(figfile)
        plt.show()

    return


# function detect_inversion_clusters attempts to detect cluster positions based off the 5' clipped end read spike in
# the SOR file. This function uses scipy gaussian stats to calculate a density plot and, based on some density
# threshold, finds clusters. Then, it finds the two maximum reads and calls those the inversion areas
def detect_inversion_clusters(sor_file, ptol=99, nbin_size=20000):

    # load SOR file positions and generate frequency data as int defaultdict
    pos_freq_dict = defaultdict(int)
    all_positions = list()
    with open(sor_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:

            # ignore TLEN values that are less than zero. Does this need to be within a read length?
            if int(row['TLEN']) != 0:
                pos_freq_dict[int(row['POS'])] += 1
                all_positions.append(int(row['POS']))

    # let x be the position and y be the frequency, and z be all the positions
    x, y = list(), list()
    for key in pos_freq_dict:

        x.append(float(key))
    x = np.array(x)
    z = np.array(all_positions)

    # compute a density histogram of the data. Bin size is equal to nucleotides determined by nbin_size
    seq_len = x.max() - x.min()
    sbin = int(seq_len / nbin_size)

    h_densities, den_bin_edges = np.histogram(z, bins=sbin, density=True)
    # h_counts, count_bin_edges = np.histogram(z, bins=sbin)

    # from here, determine some cutoff density value that identifies our clusters based of percentile ptol
    perc = np.percentile(h_densities, ptol)
    # cperc = np.percentile(h_counts, ptol)
    bin_length = den_bin_edges[1]-den_bin_edges[0]

    # show an overview plot that shows the processing of the data density histogram
    # Overview plot of the original histogram showing the percentile cutoff
    plt.plot(h_densities)
    plt.axhline(perc, color='red')
    plt.xlabel("Bin Number")
    plt.ylabel("Bin Density")
    plt.show()

    # add the left-sided bin edges to a list; these represent the left side of a potential cluster
    cluster_pos = list()
    for i in range(0, sbin):
        if h_densities[i] > perc:
            cluster_pos.append(int(den_bin_edges[i]))

    # now make an array over this region and draw our histogram over this cluster range and try to kde it
    for lpos in cluster_pos:

        # set the viewing stage to the length of the cluster
        xmin, xmax = lpos, lpos + bin_length

        # create an array that contains the histogram data of the positions here, and find the maximum two values
        cx = list()
        fmax1, fmax1_pos, fmax2, fmax2_pos = 0, 0, 0, 0
        for key in pos_freq_dict:
            if (key > xmin) and (key < xmax):
                for i in range(0, pos_freq_dict[key]):
                    cx.append(key)
        cx = np.array(cx)

        # now lets compute another density histogram over some number of bins and find the two highest read densities
        # in our cluster array

        c_densities, c_bin_edges = np.histogram(cx, bins=50, density=True)
        dmax1, dmax2, dmaxpos1, dmaxpos2 = 0.0, 0.0, 0.0, 0.0
        for i in range(0, len(c_densities)):
            den = c_densities[i]
            if den > dmax1:
                dmax1 = den
                dmaxpos1 = c_bin_edges[i]
            elif den > dmax2:
                dmax2 = den
                dmaxpos2 = c_bin_edges[i]

        # Ideally, the number of bins shouldn't hold much more than one value. What to do?
        sns.distplot(cx, bins=50)
        plt.axvline(dmaxpos1, color='red')
        plt.axvline(dmaxpos2, color='green')
        plt.show()


def detect_inversion_clusters_interactive(sor_file, nbin_size=20000):

    # class HLineBuilder allows us to define a density cutoff in the initial screen.
    class HLineBuilder:
        def __init__(self, line, x_bin):
            self.line = line
            self.xs = (0, x_bin)
            self.ys = line.get_ydata()
            self.cid = line.figure.canvas.mpl_connect('button_press_event', self)

        def __call__(self, event):
            if event.inaxes != self.line.axes: return
            y1, y2 = event.ydata, event.ydata
            self.line.set_data(self.xs, (y1, y2))
            self.y_final = y1
            self.line.figure.canvas.draw()

    # class VLineBuilder allows us to corner in on a refined cluster
    class VLineBuilder:
        def __init__(self, line, y_bin):
            self.line = line
            self.xs = line.get_xdata()
            self.ys = (0, y_bin)
            self.cid = line.figure.canvas.mpl_connect('button_press_event', self)

        def __call__(self, event):
            if event.inaxes != self.line.axes: return
            x1, x2 = event.xdata, event.xdata
            self.line.set_data((x1, x2), self.ys)
            self.x_final = x1
            self.line.figure.canvas.draw()


    # load SOR file positions and generate frequency data as int defaultdict

    pos_freq_dict = defaultdict(int)
    all_positions = list()
    with open(sor_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:

            # ignore TLEN values that are less than zero. Does this need to be within a read length?
            if int(row['TLEN']) != 0:
                pos_freq_dict[int(row['POS'])] += 1
                all_positions.append(int(row['POS']))

    # let x be the position and y be the frequency, and z be all the positions
    x, y = list(), list()
    for key in pos_freq_dict:
        x.append(float(key))
    x = np.array(x)
    z = np.array(all_positions)

    # compute a density histogram of the data. Bin size is equal to nucleotides determined by nbin_size
    seq_len = x.max() - x.min()
    sbin = int(seq_len / nbin_size)

    h_densities, den_bin_edges = np.histogram(z, bins=sbin, density=True)
    # h_counts, count_bin_edges = np.histogram(z, bins=sbin)

    # from here, determine some cutoff density value that identifies our clusters based of percentile ptol
    # perc = np.percentile(h_densities, ptol)
    # cperc = np.percentile(h_counts, ptol)
    bin_length = den_bin_edges[1] - den_bin_edges[0]

    # show an overview plot that shows the processing of the data density histogram
    # Overview plot of the original histogram showing the percentile cutoff

    fig, ax1 = plt.subplots()

    ax1.plot(h_densities)

    line, = ax1.plot([0], [0])  # empty line
    r = HLineBuilder(line, sbin)

    plt.show()
    perc = r.y_final

    # add the left-sided bin edges to a list; these represent the left side of a potential cluster
    cluster_pos = list()
    for i in range(0, sbin):
        if h_densities[i] > perc:
            cluster_pos.append(int(den_bin_edges[i]))

    # now make an array over this region and draw our histogram over this cluster range and try to kde it
    for lpos in cluster_pos:

        # set the viewing stage to the length of the cluster
        xmin, xmax = lpos, lpos + bin_length

        # create an array that contains the histogram data of the positions here, and find the maximum two values
        cx = list()
        for key in pos_freq_dict:
            if (key > xmin) and (key < xmax):
                for i in range(0, pos_freq_dict[key]-1):
                    cx.append(key)
        cx = np.array(cx)

        # now lets compute another density histogram over some number of bins and find the two highest read densities
        # in our cluster array

        c_densities, c_bin_edges = np.histogram(cx, bins=500, density=True)
        dmax1, dmax2, dmaxpos1, dmaxpos2 = 0.0, 0.0, 0.0, 0.0
        for i in range(0, len(c_densities)):
            den = c_densities[i]
            if den > dmax1:
                dmax1 = den
            elif den > dmax2:
                dmax2 = den

        # Ideally, the number of bins shouldn't hold much more than one value. What to do?
        sns.distplot(cx, kde=False, bins=500, norm_hist=True)
        # sns.kdeplot(cx, shade=True, bw=0.1)

        # Okay, so from here, we want to guess at inversion positions.
        # To do this, lets first find densities along this cluster that exceed some background density

        bkrd_perc = np.percentile(c_densities, 99)
        bin_pos, rest_bins = list(), list()
        for i in range(0, len(c_densities)):
            if c_densities[i] > bkrd_perc:
                bin_pos.append(c_bin_edges[i])
                rest_bins.append(c_bin_edges[i])
        plt.axhline(bkrd_perc)
        plt.show()


        # if we only got one or zero bins, then it's a shit cluster.
        if len(bin_pos) < 2:
            print("Not enough bins found!")
        else:

            # Then, let's see if these density positions lie within 5000nt (or some value) of each other

            bin_pairs = list()
            for i in range(0, len(bin_pos)-1):
                this_bin = bin_pos[i]
                rest_bins.remove(this_bin)
                for bin in rest_bins:
                    bin_pairs.append((this_bin, bin))

            for pair in bin_pairs:
                if abs(pair[1] - pair[0]) > 5000:
                    bin_pairs.remove(pair)

            # Now, find the bin pair that maximizes the read density
            bin_pair_density_max = 0.0
            for bin1, bin2 in bin_pairs:
                bin1d = c_densities[np.where(c_bin_edges == bin1)[0][0]]
                bin2d = c_densities[np.where(c_bin_edges == bin2)[0][0]]

                bin_pair_density = bin1d + bin2d
                if bin_pair_density > bin_pair_density_max:
                    bin_pair_density_max = bin_pair_density
                    bin_max_pair = (bin1, bin2)

            print("Bin max pair:", bin_max_pair)

            # Finally, within each bin, find the original positional value that has the highest read count
            # for most clusters, this works fine. However, for some, the bin doesn't contain the positional
            # data, which is absurd. So I'll relax it a bit.
            inv_pos = list()
            p_bin_length = c_bin_edges[1] - c_bin_edges[0]
            for box in bin_max_pair:
                inv_pos_candidates = list()
                l_box = box - 0.5 * p_bin_length
                r_box = box + 1.5 * p_bin_length

                for pos in pos_freq_dict:
                    check_pos = float(pos)
                    if check_pos > l_box:
                        if check_pos < r_box:
                            inv_pos_candidates.append(pos)
                inv_pos.append(sorted(inv_pos_candidates)[len(inv_pos_candidates)-1])

            print("Best guess at inversion positions:", inv_pos)
            plt.show()

            # If we do, lets draw a final image showing the vertical lines outlining the genomic positions of the
            # inversion site, a gaussian curve, and a gene annotating table :)

            # build our inv array
            inv_x = list()
            for pos in pos_freq_dict:
                if pos > (inv_pos[0] - 5000):
                    if pos < (inv_pos[1] + 5000):
                        for i in range(0, pos_freq_dict[pos] - 1):
                            inv_x.append(pos)
            inv_x = np.array(inv_x)

            # generate a histogram plot
            sns.distplot(inv_x, kde=False, norm_hist=True, bins=50)
            sns.kdeplot(inv_x, bw=0.5)
            plt.axvline(inv_pos[0])
            plt.axvline(inv_pos[1])
            plt.show()











