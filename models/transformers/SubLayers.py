import torch.nn as nn
import torch.nn.functional as F

import models.transformer.Constants as Constants
from models.transformer.Modules import ScaledDotProductAttention


class MultiHeadAttention(nn.Module):
    """ Multi-Head Attention module """

    def __init__(self, num_head_of_THP, dim_of_THP, dim_k_of_THP, dim_v_of_THP, dropout=0.1, normalize_before=True):
        super().__init__()

        self.normalize_before = normalize_before
        self.num_head_of_THP = num_head_of_THP
        self.dim_k_of_THP = dim_k_of_THP
        self.dim_v_of_THP = dim_v_of_THP

        self.w_qs = nn.Linear(dim_of_THP, num_head_of_THP * dim_k_of_THP, bias=False)
        self.w_ks = nn.Linear(dim_of_THP, num_head_of_THP * dim_k_of_THP, bias=False)
        self.w_vs = nn.Linear(dim_of_THP, num_head_of_THP * dim_v_of_THP, bias=False)
        nn.init.xavier_uniform_(self.w_qs.weight)
        nn.init.xavier_uniform_(self.w_ks.weight)
        nn.init.xavier_uniform_(self.w_vs.weight)

        self.fc = nn.Linear(dim_v_of_THP * num_head_of_THP, dim_of_THP)
        nn.init.xavier_uniform_(self.fc.weight)

        self.attention = ScaledDotProductAttention(temperature=dim_k_of_THP ** 0.5, attn_dropout=dropout)

        self.layer_norm = nn.LayerNorm(dim_of_THP, eps=1e-6)
        self.dropout = nn.Dropout(dropout)

    def forward(self, q, k, v, mask=None):
        dim_k_of_THP, dim_v_of_THP, num_head_of_THP = self.dim_k_of_THP, self.dim_v_of_THP, self.num_head_of_THP
        sz_b, len_q, len_k, len_v = q.size(0), q.size(1), k.size(1), v.size(1)

        residual = q
        if self.normalize_before:
            q = self.layer_norm(q)

        # Pass through the pre-attention projection: b x lq x (n*dv)
        # Separate different heads: b x lq x n x dv
        q = self.w_qs(q).view(sz_b, len_q, num_head_of_THP, dim_k_of_THP)
        k = self.w_ks(k).view(sz_b, len_k, num_head_of_THP, dim_k_of_THP)
        v = self.w_vs(v).view(sz_b, len_v, num_head_of_THP, dim_v_of_THP)

        # Transpose for attention dot product: b x n x lq x dv
        q, k, v = q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)

        if mask is not None:
            mask = mask.unsqueeze(1)  # For head axis broadcasting.

        output, attn = self.attention(q, k, v, mask=mask)
        # Transpose to move the head dimension back: b x lq x n x dv
        # Combine the last two dimensions to concatenate all the heads together: b x lq x (n*dv)
        output = output.transpose(1, 2).contiguous().view(sz_b, len_q, -1)
        output = self.dropout(self.fc(output))
        output += residual

        if not self.normalize_before:
            output = self.layer_norm(output)
        return output, attn


class PositionwiseFeedForward(nn.Module):
    """ Two-layer position-wise feed-forward neural network. """

    def __init__(self, d_in, dim_inner_of_THP, dropout=0.1, normalize_before=True):
        super().__init__()

        self.normalize_before = normalize_before

        self.w_1 = nn.Linear(d_in, dim_inner_of_THP)
        self.w_2 = nn.Linear(dim_inner_of_THP, d_in)

        self.layer_norm = nn.LayerNorm(d_in, eps=1e-6)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        residual = x
        if self.normalize_before:
            x = self.layer_norm(x)

        x = F.gelu(self.w_1(x))
        x = self.dropout(x)
        x = self.w_2(x)
        x = self.dropout(x)
        x = x + residual

        if not self.normalize_before:
            x = self.layer_norm(x)
        return x
