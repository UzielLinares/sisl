"""
Class implementation for an orbital system with, and without spin
"""
from __future__ import print_function, division

import warnings
from numbers import Integral
import itertools as itools

import numpy as np
import scipy.linalg as sli
from scipy.sparse import isspmatrix, csr_matrix
import scipy.sparse.linalg as ssli

from sisl._help import get_dtype
from sisl._help import _zip as zip, _range as range
from sisl.sparse import SparseCSR, ispmatrix, ispmatrixd
from sisl.sparse_geometry import SparseOrbital
from .spin import Spin
from .brillouinzone import BrillouinZone

__all__ = ['SparseOrbitalBZ', 'SparseOrbitalBZSpin']


class SparseOrbitalBZ(SparseOrbital):
    """ Sparse object containing the orbital connections in a Brillouin zone

    It contains an intrinsic sparse matrix of the physical elements.

    Assigning or changing elements is as easy as with
    standard ``numpy`` assignments:

    >>> S = SparseOrbitalBZ(...)
    >>> S[1,2] = 0.1

    which assigns 0.1 as the element between orbital 2 and 3.
    (remember that Python is 0-based elements).
    """

    def __init__(self, geom, dim=1, dtype=None, nnzpr=None, **kwargs):
        """Create SparseOrbitalB model from geometry

        Initializes an object using the ``geom`` object
        as the underlying geometry for the parameters that connects orbital elements.
        """
        self._geom = geom

        self._orthogonal = kwargs.get('orthogonal', True)

        # Get true dimension
        if not self.orthogonal:
            dim = dim + 1

        # Initialize the sparsity pattern
        self.reset(dim, dtype, nnzpr)

        if self.orthogonal:
            # Wrapper for always enabling creating an overlap
            # matrix. For orthogonal cases it is simply the diagonal
            # matrix
            def diagonal_Sk(self, k=(0, 0, 0), dtype=None, **kwargs):
                """ For an orthogonal case we always return the identity matrix """
                if dtype is None:
                    dtype = np.float64
                S = csr_matrix((len(self), len(self)), dtype=dtype)
                S.setdiag(1.)
                return S
            self.Sk = diagonal_Sk
            self.S_idx = -1
        else:
            dim = dim - 1
            self.S_idx = dim

        self.Pk = self._Pk

    # Override to enable spin configuration and orthogonality
    def _cls_kwargs(self):
        return {'orthogonal': self.orthogonal}

    @property
    def orthogonal(self):
        """ True if the object is using an orthogonal basis """
        return self._orthogonal

    def __len__(self):
        """ Returns number of rows in the basis (if non-colinear or spin-orbit, twice the number of orbitals) """
        return self.no

    def __repr__(self):
        """ Representation of the model """
        s = self.__class__.__name__ + '{{dim: {0}, non-zero: {1}, orthogonal: {2}\n '.format(self.dim, self.nnz, self.orthogonal)
        s += repr(self.geom).replace('\n', '\n ')
        return s + '\n}'

    def _get_S(self):
        if self.orthogonal:
            return None
        self._def_dim = self.S_idx
        return self

    def _set_S(self, key, value):
        if self.orthogonal:
            return
        self._def_dim = self.S_idx
        self[key] = value

    S = property(_get_S, _set_S)

    @classmethod
    def fromsp(cls, geom, V, S=None):
        """ Read and return the object with possible overlap """
        # Calculate maximum number of connections per row
        nc = 0

        # Ensure list of csr format (to get dimensions)
        if isspmatrix(V):
            V = [V]

        # Number of dimensions
        dim = len(V)
        # Sort all indices for the passed sparse matrices
        for i in range(dim):
            V[i] = V[i].tocsr()
            V[i].sort_indices()

        # Figure out the maximum connections per
        # row to reduce number of re-allocations to 0
        for i in range(V[0].shape[0]):
            nc = max(nc, V[0][i, :].getnnz())

        # Create the sparse object
        v = cls(geom, dim, V[0].dtype, nc, orthogonal=S is None)

        for i in range(dim):
            for jo, io, vv in ispmatrixd(H[i]):
                v[jo, io, i] = vv

        if not S is None:
            for jo, io, vv in ispmatrixd(S):
                v.S[jo, io] = vv

        return v

    # Create iterations on entire set of orbitals
    def iter(self, local=False):
        """ Iterations of the orbital space in the geometry, two indices from loop

        An iterator returning the current atomic index and the corresponding
        orbital index.

        >>> for ia, io in self:

        In the above case `io` always belongs to atom `ia` and `ia` may be
        repeated according to the number of orbitals associated with
        the atom `ia`.

        Parameters
        ----------
        local : `bool=False`
           whether the orbital index is the global index, or the local index relative to 
           the atom it resides on.
        """
        for ia, io in self.geom.iter_orbitals(local=local):
            yield ia, io

    __iter__ = iter

    def _Pk(self, k=(0, 0, 0), dtype=None, gauge='R', _dim=0):
        """ Sparse matrix (``scipy.sparse.csr_matrix``) at `k` for a polarized system

        Parameters
        ----------
        k: ``array_like``, `[0,0,0]`
           k-point 
        spin: ``int``, `0`
           the spin-index of the quantity
        dtype : ``numpy.dtype``
           default to `numpy.complex128`
        gauge : str, 'R'
           chosen gauge
        """
        if dtype is None:
            dtype = np.complex128

        if gauge != 'R':
            raise ValueError('Only the cell vector gauge has been implemented')

        k = np.asarray(k, np.float64)
        k.shape = (-1,)

        if not np.allclose(k, 0.):
            if np.dtype(dtype).kind != 'c':
                raise ValueError(self.__class__.__name__ + " setup at k different from Gamma requires a complex matrix")

        exp = np.exp
        dot = np.dot

        # Setup the quantity for this k-point
        Vf = self.tocsr(_dim)

        # size of matrix
        no = len(self)

        V = csr_matrix((no, no), dtype=dtype)

        # Get the reciprocal lattice vectors dotted with k
        kr = dot(self.rcell, k)
        for si, isc in self.sc:
            phase = exp(-1j * dot(kr, dot(self.cell, isc)))

            V += Vf[:, si * no:(si + 1) * no] * phase

        del Vf

        return V

    def _Sk(self, k=(0, 0, 0), dtype=None, gauge='R'):
        """ Overlap matrix in a ``scipy.sparse.csr_matrix`` at `k`.

        Parameters
        ----------
        k: ``array_like``, `[0,0,0]`
           k-point 
        dtype : ``numpy.dtype``
           default to `numpy.complex128`
        gauge : str, 'R'
           chosen gauge
        """
        return self._Pk(k, dtype=dtype, gauge=gauge, _dim=self.S_idx)

    def eigh(self, k=(0, 0, 0),
             atoms=None, gauge='R', eigvals_only=True,
             overwrite_a=True, overwrite_b=True,
             *args, **kwargs):
        """ Returns the eigenvalues of the physical quantity

        Setup the system and overlap matrix with respect to
        the given k-point, then reduce the space to the specified atoms
        and calculate the eigenvalues.

        All subsequent arguments gets passed directly to :code:`scipy.linalg.eigh`
        """

        # First we check if the k-point is a BrillouinZone object
        if isinstance(k, BrillouinZone):
            # Pre-allocate the eigenvalue spectrum
            eig = np.empty([len(k), len(self)], np.float64)
            for i, k_ in enumerate(k):
                eig[i, :] = self.eigh(k_, atoms=atoms, gauge=gauge,
                                      eigvals_only=eigvals_only,
                                      overwrite_a=overwrite_a, overwrite_b=overwrite_b,
                                      *args, **kwargs)
            return eig

        P = self.Pk(k=k, gauge=gauge)
        if not self.orthogonal:
            S = self.Sk(k=k, gauge=gauge)
        # Reduce sparsity pattern
        if not atoms is None:
            orbs = self.a2o(atoms)
            # Reduce space
            P = P[orbs, orbs]
            if not self.orthogonal:
                S = S[orbs, orbs]
        if self.orthogonal:
            return sli.eigh(P.todense(),
                *args,
                eigvals_only=eigvals_only,
                overwrite_a=overwrite_a,
                **kwargs)

        return sli.eigh(P.todense(), S.todense(),
            *args,
            eigvals_only=eigvals_only,
            overwrite_a=overwrite_a,
            overwrite_b=overwrite_b,
            **kwargs)

    def eigsh(self, k=(0, 0, 0), n=10,
              atoms=None, gauge='R', eigvals_only=True,
              *args, **kwargs):
        """ Calculates a subset of eigenvalues of the physical quantity  (default 10)

        Setup the quantity and overlap matrix with respect to
        the given k-point, then reduce the space to the specified atoms
        and calculate a subset of the eigenvalues using the sparse algorithms.

        All subsequent arguments gets passed directly to :code:`scipy.linalg.eigsh`
        """

        # First we check if the k-point is a BrillouinZone object
        if isinstance(k, BrillouinZone):
            # Pre-allocate the eigenvalue spectrum
            eig = np.empty([len(k), n], np.float64)
            for i, k_ in enumerate(k):
                eig[i, :] = self.eigsh(k_, n=n,
                                       atoms=atoms, gauge=gauge,
                                       eigvals_only=eigvals_only,
                                       *args, **kwargs)
            return eig

        # We always request the smallest eigenvalues...
        kwargs.update({'which': kwargs.get('which', 'SM')})

        P = self.Pk(k=k, gauge=gauge)
        if not self.orthogonal:
            raise ValueError("The sparsity pattern is non-orthogonal, you cannot use the Arnoldi procedure with scipy")

        # Reduce sparsity pattern
        if not atoms is None:
            orbs = self.a2o(atoms)
            # Reduce space
            P = P[orbs, orbs]

        return ssli.eigsh(P, k=n,
                          *args,
                          return_eigenvectors=not eigvals_only,
                          **kwargs)


class SparseOrbitalBZSpin(SparseOrbitalBZ):
    """ Sparse object containing the orbital connections in a Brillouin zone with possible spin-components

    It contains an intrinsic sparse matrix of the physical elements.

    Assigning or changing elements is as easy as with
    standard ``numpy`` assignments:

    >>> S = SparseOrbitalBZSpin(...)
    >>> S[1,2] = 0.1

    which assigns 0.1 as the element between orbital 2 and 3.
    (remember that Python is 0-based elements).
    """

    def __init__(self, geom, dim=1, dtype=None, nnzpr=None, **kwargs):
        """Create SparseOrbitalBZSpin model from geometry

        Initializes an object using the ``geom`` object
        as the underlying geometry for the parameters that connects orbital elements.
        """
        # Check that the passed parameters are correct
        self._spin = Spin(kwargs.get('spin', dim), dtype)

        super(SparseOrbitalBZSpin, self).__init__(geom, len(self.spin), self.spin.dtype, nnzpr, **kwargs)

        if self.spin.is_unpolarized:
            self.UP = 0
            self.DOWN = 0
            self.Pk = self._Pk_unpolarized
            self.Sk = self._Sk
        elif self.spin.is_polarized:
            self.UP = 0
            self.DOWN = 1
            self.Pk = self._Pk_polarized
            self.Sk = self._Sk
        elif self.spin.is_noncolinear:
            if self.spin.dkind == 'f':
                self.M11 = 0
                self.M22 = 1
                self.M12r = 2
                self.M12i = 3
            else:
                self.M11 = 0
                self.M22 = 1
                self.M12 = 2
                raise ValueError('Currently not implemented')
            self.Pk = self._Pk_non_collinear
            self.Sk = self._Sk_non_collinear
        elif self.spin.is_spinorbit:
            if self.spin.dkind == 'f':
                self.M11r = 0
                self.M22r = 1
                self.M21r = 2
                self.M21_i = 3
                self.M11i = 4
                self.M22i = 5
                self.M12r = 6
                self.M12i = 7
            else:
                self.M11 = 0
                self.M22 = 1
                self.M12 = 2
                self.M21 = 3
                raise ValueError('Currently not implemented')
            # The overlap is the same as non-collinear
            self.Pk = self._Pk_spin_orbit
            self.Sk = self._Sk_non_collinear

    # Override to enable spin configuration and orthogonality
    def _cls_kwargs(self):
        return {'spin': self.spin, 'orthogonal': self.orthogonal}

    @property
    def spin(self):
        """ Spin class """
        return self._spin

    def __len__(self):
        """ Returns number of rows in the basis (if non-colinear or spin-orbit, twice the number of orbitals) """
        if self.spin.spin > 2:
            return self.no * 2
        return self.no

    def __repr__(self):
        """ Representation of the model """
        s = self.__class__.__name__ + '{{spin: {0}, non-zero: {1}, orthogonal: {2}\n '.format(self.spin.spin, self.nnz, self.orthogonal)
        s += repr(self.geom).replace('\n', '\n ')
        return s + '\n}'

    @classmethod
    def fromsp(cls, geom, P, S=None):
        """ Read and return the object with possible overlap """
        # Calculate maximum number of connections per row
        nc = 0

        # Ensure list of csr format (to get dimensions)
        if isspmatrix(P):
            P = [P]

        # Number of dimensions
        dim = len(P)
        # Sort all indices for the passed sparse matrices
        for i in range(dim):
            P[i] = P[i].tocsr()
            P[i].sort_indices()

        # Figure out the maximum connections per
        # row to reduce number of re-allocations to 0
        for i in range(P[0].shape[0]):
            nc = max(nc, P[0][i, :].getnnz())

        # Create the sparse object
        v = cls(geom, dim, P[0].dtype, nc, orthogonal=S is None)

        for i in range(dim):
            for jo, io, vv in ispmatrixd(P[i]):
                v[jo, io, i] = vv

        if not S is None:
            for jo, io, vv in ispmatrixd(S):
                v.S[jo, io] = vv

        return v

    def _Pk_unpolarized(self, k=(0, 0, 0), dtype=None, gauge='R'):
        """ Sparse matrix (``scipy.sparse.csr_matrix``) at `k`

        Parameters
        ----------
        k: ``array_like``, `[0,0,0]`
           k-point 
        dtype : ``numpy.dtype``
           default to `numpy.complex128`
        gauge : str, 'R'
           chosen gauge
        """
        return self._Pk_polarized(k, dtype=dtype, gauge=gauge)

    def _Pk_polarized(self, k=(0, 0, 0), spin=0, dtype=None, gauge='R'):
        """ Sparse matrix (``scipy.sparse.csr_matrix``) at `k` for a polarized system

        Parameters
        ----------
        k: ``array_like``, `[0,0,0]`
           k-point 
        spin: ``int``, `0`
           the spin-index of the quantity
        dtype : ``numpy.dtype``
           default to `numpy.complex128`
        gauge : str, 'R'
           chosen gauge
        """
        if dtype is None:
            dtype = np.complex128

        if gauge != 'R':
            raise ValueError('Only the cell vector gauge has been implemented')

        k = np.asarray(k, np.float64)
        k.shape = (-1,)

        if not np.allclose(k, 0.):
            if np.dtype(dtype).kind != 'c':
                raise ValueError(self.__class__.__name__ + " setup at k different from Gamma requires a complex matrix")

        exp = np.exp
        dot = np.dot

        # Setup the quantity for this k-point
        Vf = self.tocsr(spin)

        # number of orbitals
        no = self.no

        V = csr_matrix((no, no), dtype=dtype)

        # Get the reciprocal lattice vectors dotted with k
        kr = dot(self.rcell, k)
        for si, isc in self.sc:
            phase = exp(-1j * dot(kr, dot(self.cell, isc)))

            V += Vf[:, si * no:(si + 1) * no] * phase

        del Vf

        return V

    def _Pk_non_collinear(self, k=(0, 0, 0), dtype=None, gauge='R'):
        """ Sparse matrix (``scipy.sparse.csr_matrix``) at `k` for a non-colinear system

        Parameters
        ----------
        k: ``array_like``, `[0,0,0]`
           k-point 
        dtype : ``numpy.dtype``
           default to `numpy.complex128`
        gauge : str, 'R'
           chosen gauge
        """
        if dtype is None:
            dtype = np.complex128

        if np.dtype(dtype).kind != 'c':
            raise ValueError("Non-colinear quantity setup requires a complex matrix")

        if gauge != 'R':
            raise ValueError('Only the cell vector gauge has been implemented')

        exp = np.exp
        dot = np.dot

        k = np.asarray(k, np.float64)
        k.shape = (-1,)

        # number of orbitals
        no = self.no

        # sparse matrix dimension (2 * self.no)
        V = csr_matrix((len(self), len(self)), dtype=dtype)

        # Get the reciprocal lattice vectors dotted with k
        kr = dot(self.rcell, k)
        for si, isc in self.sc:
            phase = exp(-1j * dot(kr, dot(self.cell, isc)))
            sl = slice(si*no, (si+1) * no, None)

            # diagonal elements
            V[::2, ::2] += self.tocsr(0)[:, sl] * phase
            V[1::2, 1::2] += self.tocsr(1)[:, sl] * phase

            # off-diagonal elements
            V1 = self.tocsr(2)[:, sl]
            V2 = self.tocsr(3)[:, sl]
            V[1::2, ::2] += (V1 - 1j * V2) * phase
            V[::2, 1::2] += (V1 + 1j * V2) * phase

            del V1, V2

        return V

    def _Pk_spin_orbit(self, k=(0, 0, 0), dtype=None, gauge='R'):
        """ Sparse matrix (``scipy.sparse.csr_matrix``) at `k` for a spin-orbit system

        Parameters
        ----------
        k: ``array_like``, `[0,0,0]`
           k-point 
        dtype : ``numpy.dtype``
           default to `numpy.complex128`
        gauge : str, 'R'
           chosen gauge
        """
        if dtype is None:
            dtype = np.complex128

        if np.dtype(dtype).kind != 'c':
            raise ValueError("Spin orbit quantity setup requires a complex matrix")

        if gauge != 'R':
            raise ValueError('Only the cell vector gauge has been implemented')

        exp = np.exp
        dot = np.dot

        k = np.asarray(k, np.float64)
        k.shape = (-1,)

        # number of orbitals
        no = self.no

        # sparse matrix dimension (2 * self.no)
        V = csr_matrix((len(self), len(self)), dtype=dtype)

        # Get the reciprocal lattice vectors dotted with k
        kr = dot(self.rcell, k)
        for si, isc in self.sc:
            phase = exp(-1j * dot(kr, dot(self.cell, isc)))
            sl = slice(si*no, (si+1) * no, None)

            # diagonal elements
            V[::2, ::2] += (self.tocsr(0)[:, sl] +
                            1j * self.tocsr(4)[:, sl]) * phase
            V[1::2, 1::2] += (self.tocsr(1)[:, sl] +
                              1j * self.tocsr(5)[:, sl]) * phase

            # lower off-diagonal elements
            V[1::2, ::2] += (self.tocsr(2)[:, sl] -
                             1j * self.tocsr(3)[:, sl]) * phase

            # upper off-diagonal elements
            V[::2, 1::2] += (self.tocsr(6)[:, sl] +
                             1j * self.tocsr(7)[:, sl]) * phase

        return V

    def _Sk(self, k=(0, 0, 0), dtype=None, gauge='R'):
        """ Overlap matrix in a ``scipy.sparse.csr_matrix`` at `k`.

        Parameters
        ----------
        k: ``array_like``, `[0,0,0]`
           k-point 
        dtype : ``numpy.dtype``
           default to `numpy.complex128`
        gauge : str, 'R'
           chosen gauge
        """
        return self._Pk_polarized(k, spin=self.S_idx, dtype=dtype, gauge=gauge)

    def _Sk_non_collinear(self, k=(0, 0, 0), dtype=None, gauge='R'):
        """ Overlap matrix in a ``scipy.sparse.csr_matrix`` at `k`.

        Parameters
        ----------
        k: ``array_like``, `[0,0,0]`
           k-point 
        dtype : ``numpy.dtype``
           default to `numpy.complex128`
        gauge : str, 'R'
           chosen gauge
        """
        if dtype is None:
            dtype = np.complex128

        if not np.allclose(k, 0.):
            if np.dtype(dtype).kind != 'c':
                raise ValueError("Overlap setup at k different from Gamma requires a complex matrix")

        if gauge != 'R':
            raise ValueError('Only the cell vector gauge has been implemented')

        exp = np.exp
        dot = np.dot

        k = np.asarray(k, np.float64)
        k.shape = (-1,)

        # Get the overlap matrix
        Sf = self.tocsr(self.S_idx)

        # number of orbitals
        no = self.no

        S = csr_matrix((len(self), len(self)), dtype=dtype)

        # Get the reciprocal lattice vectors dotted with k
        kr = dot(self.rcell, k)
        for si, isc in self.sc:
            phase = exp(-1j * dot(kr, dot(self.cell, isc)))

            sf = Sf[:, si*no:(si+1)*no] * phase

            S[::2, ::2] += sf
            S[1::2, 1::2] += sf

            del sf

        return S

    def eigh(self, k=(0, 0, 0),
             atoms=None, gauge='R', eigvals_only=True,
             overwrite_a=True, overwrite_b=True,
             *args, **kwargs):
        """ Returns the eigenvalues of the physical quantity

        Setup the system and overlap matrix with respect to
        the given k-point, then reduce the space to the specified atoms
        and calculate the eigenvalues.

        All subsequent arguments gets passed directly to :code:`scipy.linalg.eigh`
        """

        # First we check if the k-point is a BrillouinZone object
        if isinstance(k, BrillouinZone):
            # Pre-allocate the eigenvalue spectrum
            eig = np.empty([len(k), len(self)], np.float64)
            for i, k_ in enumerate(k):
                eig[i, :] = self.eigh(k_, atoms=atoms, gauge=gauge,
                                      eigvals_only=eigvals_only,
                                      overwrite_a=overwrite_a, overwrite_b=overwrite_b,
                                      *args, **kwargs)
            return eig

        if self.spin.kind == Spin.POLARIZED:
            P = self.Pk(k=k, spin=kwargs.pop('spin', 0), gauge=gauge)
        else:
            P = self.Pk(k=k, gauge=gauge)
        if not self.orthogonal:
            S = self.Sk(k=k, gauge=gauge)
        # Reduce sparsity pattern
        if not atoms is None:
            orbs = self.a2o(atoms)
            # Reduce space
            P = P[orbs, orbs]
            if not self.orthogonal:
                S = S[orbs, orbs]
        if self.orthogonal:
            return sli.eigh(P.todense(),
                *args,
                eigvals_only=eigvals_only,
                overwrite_a=overwrite_a,
                **kwargs)

        return sli.eigh(P.todense(), S.todense(),
            *args,
            eigvals_only=eigvals_only,
            overwrite_a=overwrite_a,
            overwrite_b=overwrite_b,
            **kwargs)

    def eigsh(self, k=(0, 0, 0), n=10,
              atoms=None, gauge='R', eigvals_only=True,
              *args, **kwargs):
        """ Calculates a subset of eigenvalues of the physical quantity  (default 10)

        Setup the quantity and overlap matrix with respect to
        the given k-point, then reduce the space to the specified atoms
        and calculate a subset of the eigenvalues using the sparse algorithms.

        All subsequent arguments gets passed directly to :code:`scipy.linalg.eigsh`
        """

        # First we check if the k-point is a BrillouinZone object
        if isinstance(k, BrillouinZone):
            # Pre-allocate the eigenvalue spectrum
            eig = np.empty([len(k), n], np.float64)
            for i, k_ in enumerate(k):
                eig[i, :] = self.eigsh(k_, n=n,
                                       atoms=atoms, gauge=gauge,
                                       eigvals_only=eigvals_only,
                                       *args, **kwargs)
            return eig

        # We always request the smallest eigenvalues...
        kwargs.update({'which': kwargs.get('which', 'SM')})

        if self.spin.kind == Spin.POLARIZED:
            P = self.Pk(k=k, spin=kwargs.pop('spin', 0), gauge=gauge)
        else:
            P = self.Pk(k=k, gauge=gauge)
        if not self.orthogonal:
            raise ValueError("The sparsity pattern is non-orthogonal, you cannot use the Arnoldi procedure with scipy")

        # Reduce sparsity pattern
        if not atoms is None:
            orbs = self.a2o(atoms)
            # Reduce space
            P = P[orbs, orbs]

        return ssli.eigsh(P, k=n,
                          *args,
                          return_eigenvectors=not eigvals_only,
                          **kwargs)
