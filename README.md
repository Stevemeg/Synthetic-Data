#  Synthetic Medical Data Generation System

> **Generating privacy-safe, high-quality synthetic medical data using GANs, VAEs, and Diffusion Models — across imaging, tabular, and genomic modalities.**

---

##  The Problem

Medical AI is bottlenecked by **data scarcity and privacy restrictions**. Hospitals can't share patient data across institutions due to HIPAA/GDPR, and most public medical datasets are too small to train robust AI models.

**This project solves that** by generating realistic synthetic medical data that:
- Preserves the statistical properties of real patient data
- Contains **zero real patient information**
- Can be freely shared and used to train AI systems

---

##  What I Built

A production-grade pipeline that trains generative models on real medical datasets and uses them to produce unlimited synthetic data — across **3 data modalities**:

| Modality | What's Generated | Model Used |
|---|---|---|
| **Medical Imaging** | Brain MRIs, Chest X-rays, Skin Cancer images | DCGAN, cGAN |
| **Clinical Tabular Data** | Patient records (diabetes, heart disease, stroke, sepsis) | TabDDPM, CopulaGAN |
| **Genomic Data** | Gene expression profiles (breast cancer) | TVAE |

---

##  Models & Why I Chose Them

### DCGAN (Deep Convolutional GAN)
Used for **medical image generation**. Convolutional layers let the generator learn spatial structures like tumor shapes and tissue textures. Batch normalization keeps training stable.

### Conditional GAN (cGAN)
An extension of DCGAN where generation is **conditioned on class labels** (e.g., "generate a pneumonia X-ray" vs. "generate a healthy X-ray"). Gives precise control over the output.

### TVAE (Tabular Variational Autoencoder)
Used for **genomic and gene expression data**. Encodes high-dimensional gene profiles into a compact latent space, then decodes to generate new realistic profiles. Also supports **differential privacy** enforcement.

### TabDDPM (Diffusion Model for Tabular Data)
A **diffusion-based** generator for clinical tabular datasets. Learns to reverse a noise process to recreate data, resulting in better distribution matching than standard GANs for structured data.

### CopulaGAN
A GAN variant that explicitly models **correlations between features** using copula functions — critical for clinical data where variables like age, BMI, and blood pressure are interdependent.

---

##  Datasets Used

**Medical Imaging**
- Brain MRI Dataset
- Chest X-ray Pneumonia Dataset (Kaggle)
- Skin Cancer HAM10000 Dataset

**Clinical Tabular**
- Diabetes 130-US Hospitals Dataset
- Heart Disease UCI Dataset
- Stroke Prediction Dataset
- Sepsis Survival Dataset

**Genomic**
- TCGA-BRCA Gene Expression Dataset
- Microarray Gene Expression Dataset (GSE45827)

---

##  Pipeline Architecture

```
Raw Medical Dataset
        │
        ▼
  Preprocessing
  (normalization, encoding, image resizing, missing value handling)
        │
        ▼
  Model Training
  (GAN / VAE / Diffusion)
        │
        ▼
  Save Trained Generator
        │
        ▼
  Generate Synthetic Samples
        │
        ▼
  Evaluation (SSIM / SDV Quality Report / Statistical Comparison)
        │
        ▼
  Store & Export Synthetic Dataset
```

---

##  How I Evaluated Quality

Different metrics for different data types:

**Images (DCGAN / cGAN)**
- **SSIM (Structural Similarity Index)** — measures perceptual similarity to real images
- Visual inspection of generated samples
- Class distribution matching (are generated labels balanced?)

**Tabular & Genomic Data (TVAE / TabDDPM / CopulaGAN)**
- **SDV Quality Report** — industry-standard synthetic data evaluation
- Statistical distribution comparison (mean, std, skew per feature)
- Feature correlation matrix comparison (real vs. synthetic)
- SDV Diagnostic Report for validity checks

---

##  Tech Stack

| Category | Tools |
|---|---|
| Languages | Python |
| Deep Learning | PyTorch, TensorFlow |
| Synthetic Data Libraries | SDV, ydata-synthetic |
| Data Processing | NumPy, Pandas, Scikit-learn |
| Visualization | Matplotlib, Seaborn |

---

##  Project Structure

```
synthetic-data-generation/
│
├── imaging_models/         # DCGAN and cGAN implementations
├── tabular_models/         # TabDDPM, CopulaGAN implementations
├── genomics_models/        # TVAE for gene expression data
├── preprocessing/          # Data cleaning and transformation scripts
├── generated_data/         # Output synthetic datasets
├── trained_models/         # Saved model checkpoints
├── evaluation/             # Evaluation scripts and quality reports
├── notebooks/              # Jupyter notebooks for exploration
└── README.md
```

---

##  Key Results

- Successfully generated synthetic data across **all 9 datasets**
- Synthetic images visually indistinguishable from real samples (validated via SSIM)
- Tabular synthetic data matched real distributions across all features per SDV Quality Report
- Genomic synthetic data preserved gene-gene correlation structure
- Downstream AI models trained on synthetic data showed **comparable performance** to those trained on real data

---

##  Future Work

- [ ] Deploy as a REST API so researchers can request synthetic data on demand
- [ ] Add a web interface for non-technical users
- [ ] Integrate with vector databases for fast retrieval
- [ ] Automate the full training → generation → evaluation pipeline
- [ ] Cloud deployment (AWS / GCP)

---

##  Why This Matters

This system directly addresses a **critical bottleneck in healthcare AI**: the inability to share patient data. By generating realistic, privacy-safe synthetic datasets, it enables hospitals, researchers, and AI teams to collaborate and build better models — without ever exposing real patient information.
