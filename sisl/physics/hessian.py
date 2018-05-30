from __future__ import print_function, division

import numpy as np

from .sparse import SparseOrbitalBZ

__all__ = ['Hessian', 'DynamicalMatrix']


class Hessian(SparseOrbitalBZ):
    """ Dynamical matrix of a geometry """

    def __init__(self, geometry, dim=1, dtype=None, nnzpr=None, **kwargs):
        super(Hessian, self).__init__(geometry, dim, dtype, nnzpr, **kwargs)

        self.Hk = self._Pk
        self.dHk = self.dPk
        self.ddHk = self.ddPk

    def Hk(self, k=(0, 0, 0), dtype=None, gauge='R', format='csr', *args, **kwargs):
        r""" Setup the Hessian matrix for a given k-point

        Creation and return of the Hessian matrix for a given k-point (default to Gamma).

        Notes
        -----

        Currently the implemented gauge for the k-point is the cell vector gauge:

        .. math::
           \mathbf H(k) = \mathbf H_{\nu\mu} e^{i q R}

        where :math:`R` is an integer times the cell vector and :math:`\nu`, :math:`\mu` are orbital indices.

        Another possible gauge is the orbital distance which can be written as

        .. math::
           \mathbf H(k) = \mathbf H_{\nu\mu} e^{i k r}

        where :math:`r` is the distance between the orbitals.
        Currently this gauge is not implemented (yet).

        Parameters
        ----------
        k : array_like
           the k-point to setup the Hessian matrix at
        dtype : numpy.dtype , optional
           the data type of the returned matrix. Do NOT request non-complex
           data-type for non-Gamma k.
           The default data-type is `numpy.complex128`
        gauge : {'R', 'r'}
           the chosen gauge, `R` for cell vector gauge, and `r` for orbital distance
           gauge.
        format : {'csr', 'array', 'dense', 'coo', ...}
           the returned format of the matrix, defaulting to the ``scipy.sparse.csr_matrix``,
           however if one always requires operations on dense matrices, one can always
           return in `numpy.ndarray` (`'array'`) or `numpy.matrix` (`'dense'`).

        See Also
        --------
        dHk : Hessian derivative with respect to `k`
        ddHk : Hessian double derivative with respect to `k`

        Returns
        -------
        object : the Hessian matrix at :math:`k`. The returned object depends on `format`.
        """
        pass

    def dHk(self, k=(0, 0, 0), dtype=None, gauge='R', format='csr', *args, **kwargs):
        r""" Setup the Hessian matrix derivative for a given k-point

        Creation and return of the Hessian matrix derivative for a given k-point (default to Gamma).

        Notes
        -----

        Currently the implemented gauge for the k-point is the cell vector gauge:

        .. math::
           \nabla_k \mathbf H_\alpha(k) = i R_\alpha \mathbf H_{\nu\mu} e^{i q R}

        where :math:`R` is an integer times the cell vector and :math:`\nu`, :math:`\mu` are orbital indices.
        And :math:`\alpha` is one of the Cartesian directions.

        Another possible gauge is the orbital distance which can be written as

        .. math::
          \nabla_k \mathbf H_\alpha(k) = i r_\alpha \mathbf H_{\nu\mu} e^{i k r}

        where :math:`r` is the distance between the orbitals.
        Currently this gauge is not implemented (yet).

        Parameters
        ----------
        k : array_like
           the k-point to setup the Hessian matrix at
        dtype : numpy.dtype , optional
           the data type of the returned matrix. Do NOT request non-complex
           data-type for non-Gamma k.
           The default data-type is `numpy.complex128`
        gauge : {'R', 'r'}
           the chosen gauge, `R` for cell vector gauge, and `r` for orbital distance
           gauge.
        format : {'csr', 'array', 'dense', 'coo', ...}
           the returned format of the matrix, defaulting to the ``scipy.sparse.csr_matrix``,
           however if one always requires operations on dense matrices, one can always
           return in `numpy.ndarray` (`'array'`) or `numpy.matrix` (`'dense'`).

        See Also
        --------
        Hk : Hessian with respect to `k`
        ddHk : Hessian double derivative with respect to `k`

        Returns
        -------
        tuple : for each of the Cartesian directions a :math:`\partial \mathbf H(k)/\partial k` is returned.
        """
        pass

    def ddHk(self, k=(0, 0, 0), dtype=None, gauge='R', format='csr', *args, **kwargs):
        r""" Setup the Hessian matrix double derivative for a given k-point

        Creation and return of the Hessian matrix double derivative for a given k-point (default to Gamma).

        Notes
        -----

        Currently the implemented gauge for the k-point is the cell vector gauge:

        .. math::
           \nabla_k^2 \mathbf H_{\alpha\beta}(k) = - R_\alpha R_\beta \mathbf H_{\nu\mu} e^{i q R}

        where :math:`R` is an integer times the cell vector and :math:`\nu`, :math:`\mu` are orbital indices.
        And :math:`\alpha`, :math:`\beta` are one of the Cartesian directions.

        Another possible gauge is the orbital distance which can be written as

        .. math::
           \nabla_k^2 \mathbf H_{\alpha\beta}(k) = - r_\alpha r_\beta \mathbf H_{\nu\mu} e^{i k r}

        where :math:`r` is the distance between the orbitals.
        Currently this gauge is not implemented (yet).

        Parameters
        ----------
        k : array_like
           the k-point to setup the Hessian matrix at
        dtype : numpy.dtype , optional
           the data type of the returned matrix. Do NOT request non-complex
           data-type for non-Gamma k.
           The default data-type is `numpy.complex128`
        gauge : {'R', 'r'}
           the chosen gauge, `R` for cell vector gauge, and `r` for orbital distance
           gauge.
        format : {'csr', 'array', 'dense', 'coo', ...}
           the returned format of the matrix, defaulting to the ``scipy.sparse.csr_matrix``,
           however if one always requires operations on dense matrices, one can always
           return in `numpy.ndarray` (`'array'`) or `numpy.matrix` (`'dense'`).

        See Also
        --------
        Hk : Hessian with respect to `k`
        dHk : Hessian derivative with respect to `k`

        Returns
        -------
        tuple of tuples : for each of the Cartesian directions
        """
        pass

    def _get_H(self):
        self._def_dim = 0
        return self

    def _set_H(self, key, value):
        if len(key) == 2:
            self._def_dim = 0
        self[key] = value

    H = property(_get_H, _set_H)

    def correct_Newton(self):
        """
        Sometimes the dynamical matrix does not obey Newtons laws.

        We correct the dynamical matrix by imposing zero force.

        Correcting for Newton forces the matrix to be finalized.
        """
        from scipy.sparse import lil_matrix

        # Create UC dynamical matrix
        dyn_sc = self.tocsr(0)
        no = self.no
        d_uc = lil_matrix((no, no), dtype=dyn_sc.dtype)

        for i, _ in self.sc:
            d_uc[:, :] += dyn_sc[:, i*no: (i+1)*no]

        d_uc = d_uc.tocsc()

        # we need to correct the dynamical matrix found in GULP
        # This ensures that Newtons laws are obeyed, (i.e.
        # action == re-action)
        om = np.sqrt(self.mass)
        MM = np.empty([len(om)], np.float64)

        for ja in self.geometry:

            # Create conversion to force-constant, and revert back
            # after correcting
            MM[:] = om[:] / om[ja]
            jo = ja * 3

            # Unroll...
            H = self.H[jo, jo]
            self.H[jo, jo] = H - d_uc[jo, ::3].multiply(MM).sum()
            H = self.H[jo, jo + 1]
            self.H[jo, jo + 1] = H - d_uc[jo, 1::3].multiply(MM).sum()
            H = self.H[jo, jo + 2]
            self.H[jo, jo + 2] = H - d_uc[jo, 2::3].multiply(MM).sum()

            H = self.H[jo + 1, jo]
            self.H[jo + 1, jo] = H - d_uc[jo + 1, ::3].multiply(MM).sum()
            H = self.H[jo + 1, jo + 1]
            self.H[jo + 1, jo + 1] = H - d_uc[jo + 1, 1::3].multiply(MM).sum()
            H = self.H[jo + 1, jo + 2]
            self.H[jo + 1, jo + 2] = H - d_uc[jo + 1, 2::3].multiply(MM).sum()

            H = self.H[jo + 2, jo]
            self.H[jo + 2, jo] = H - d_uc[jo + 2, ::3].multiply(MM).sum()
            H = self.H[jo + 2, jo + 1]
            self.H[jo + 2, jo + 1] = H - d_uc[jo + 2, 1::3].multiply(MM).sum()
            H = self.H[jo + 2, jo + 2]
            self.H[jo + 2, jo + 2] = H - d_uc[jo + 2, 2::3].multiply(MM).sum()

        del d_uc

    @staticmethod
    def read(sile, *args, **kwargs):
        """ Reads Hessian from `Sile` using `read_hessian`.

        Parameters
        ----------
        sile : `Sile`, str
            a `Sile` object which will be used to read the Hessian
            and the overlap matrix (if any)
            if it is a string it will create a new sile using `get_sile`.
        * : args passed directly to ``read_hamiltonian(,**)``
        """
        # This only works because, they *must*
        # have been imported previously
        from sisl.io import get_sile, BaseSile
        if isinstance(sile, BaseSile):
            return sile.read_hessian(*args, **kwargs)
        else:
            with get_sile(sile) as fh:
                return fh.read_hessian(*args, **kwargs)

    def write(self, sile, *args, **kwargs):
        """ Writes a Hessian to the `Sile` as implemented in the :code:`Sile.write_hessian` method """
        # This only works because, they *must*
        # have been imported previously
        from sisl.io import get_sile, BaseSile
        if isinstance(sile, BaseSile):
            sile.write_hessian(self, *args, **kwargs)
        else:
            with get_sile(sile, 'w') as fh:
                fh.write_hessian(self, *args, **kwargs)


DynamicalMatrix = Hessian
