$# LS-DYNA Keyword file created by WB-LSDYNA 2026 R1
$# Data in consistent NMM units. See Solving Units in the help system for more information.
*KEYWORD
*PARAMETER_DUPLICATION
4
*DATABASE_FORMAT
$    iform   ibinary                                                      unused
         0         0                                                            
*CONTROL_TERMINATION
$   endtim    endcyc     dtmin    endeng    endmas                        unused
         1  10000000     0.001         0    100000                              
*CONTROL_TIMESTEP
$   dtinit    tssfac      isdo    tslimt     dt2ms      lctm     erode     ms1st
         0       0.9         0         0         0         0         1         0
$   dt2msf   dt2mslc     imscl              unused     rmscl     emscl      ihdo
         0         0         0                             0         0         0
*CONTROL_CONTACT
$   slsfac    rwnpal    islchk    shlthk    penopt    thkchg     orien    enmass
         0         0         1         1         1         0         2         0
$   usrstr   usrfric     nsbcs    interm     xpene     ssthk      ecdt   tiedprj
         0         0         0         0         0         0         0         0
$    sfric     dfric       edc       vfc        th     th_sf    pen_sf    unused
         0         0         0         0         0         0         0          
$   ignore    frceng   skiprwg    outseg   spotstp   spotdel   spothin   unused1
         2         1         0         1         0         1       0.5          
$     isym    nserod    rwgaps    rwgdth     rwksf      icov    swradf    ithoff
         0         0         0         0         0         0         0         0
$   shledg    pstiff    ithcnt    tdcnof     ftall                       unused2
         1         0         0         0         1                              
*CONTROL_ENERGY
$     hgen      rwen    slnten     rylen                                  unused
         2         2         2         2                                        
*CONTROL_ACCURACY
$      osu       inn    pidosu                                            unused
         0         1         0                                                 0
*CONTROL_BULK_VISCOSITY
$       q1        q2      type                                            unused
       1.5      0.06        -2                                                  
*CONTROL_SOLID
$    esort    fmatrx   niptets    swlocl                                  unused
         1         0         0         0                                        
$    pm1     pm2     pm3     pm4     pm5     pm6     pm7     pm8     pm9    pm10
       0       0       0       0       0       0       0       0       0       0
$   tet13v     rinrt    coheqc                                           unused2
         1         0         0                                                  
*CONTROL_SHELL
$   wrpang     esort     irnxx    istupd    theory       bwc     miter      proj
        20         1        -1         4         2         1         1         1
$  rotascl    intgrd    lamsht    cstyp6    tshell    nfail1    nfail4   psnfail
         0         0         0         0         0         1         1         0
$   pstupd    irquad     cntco                                            unused
         0         0         2                                                  
*CONTROL_OUTPUT
$    npopt    neecho    nrefup    iaccop     opifs    ipnint    ikedit    iflush
         1         0         0         0         0         0         0         0
$    iprtf    ierode     tet10    msgmax    ipcurv                        unused
         0         0         0         0         0                              
*CONTROL_PARALLEL
$     ncpu    numrhs    consti      para                                  unused
         0         0         1         0                                        
*CONTROL_SOLUTION
$     soln       nlq     isnan     lcint                                  unused
         0         0         0         0                                        
*CONTROL_HOURGLASS
$      ihq        qh                                                     unused1
         5       0.1                                                            
*SECTION_SOLID
$       ID    elform       aet                                           unused1
         1         1         0                                                  
*MAT_ELASTIC
$       ID        ro         E        pr        da        db         k   unused1
         1  7.85E-09    200000       0.3         0         0         0          
$Material Id = {1,{6D0ECB1B-F410-483F-84AB-EFE4BA5886E8}, Structural Steel}
*PART
$                                                             partname   unused1
                                                             SYS\Solid          
$       ID     secid       mid     eosid      hgid      grav     adopt      tmid
         1         1         1         0         0         0         0         0
*NODE
       1     12.69999985    -12.69999985     25.39999969                        
       2    -12.69999985    -12.69999985     25.39999969                        
       3     12.69999985     12.69999985     25.39999969                        
       4    -12.69999985     12.69999985     25.39999969                        
       5     12.69999985    -12.69999985      0.00000000                        
       6    -12.69999985    -12.69999985      0.00000000                        
       7     12.69999985     12.69999985      0.00000000                        
       8    -12.69999985     12.69999985      0.00000000                        
*ELEMENT_SOLID
       1       1
       1       2       4       3       5       6       8       7
*DEFINE_COORDINATE_SYSTEM
$       ID        xO        yO        zO        xL        yL        zL   unused1
        23         0         0         0         1         0         0          
$       xP        yP        zP                                           unused2
         0         1         0                                                  
*SET_NODE_LIST_TITLE
face_xmin
         2
         2         4         6         8
*SET_SEGMENT_TITLE
face_xmin
         2
         2         4         8         6
*SET_NODE_LIST_TITLE
face_xmax
         3
         1         3         5         7
*SET_SEGMENT_TITLE
face_xmax
         3
         3         1         5         7
*SET_NODE_LIST_TITLE
face_zmin
         4
         5         6         7         8
*SET_SEGMENT_TITLE
face_zmin
         4
         5         6         8         7
*SET_NODE_LIST_TITLE
face_zmax
         5
         1         2         3         4
*SET_SEGMENT_TITLE
face_zmax
         5
         2         1         3         4
*SET_NODE_LIST_TITLE
face_ymin
         6
         1         2         5         6
*SET_SEGMENT_TITLE
face_ymin
         6
         1         2         6         5
*SET_NODE_LIST_TITLE
face_ymax
         7
         3         4         7         8
*SET_SEGMENT_TITLE
face_ymax
         7
         4         3         7         8
*SET_NODE_LIST
         8
         5         6         7         8
*BOUNDARY_SPC_SET
$     nsid       cid      dofx      dofy      dofz     dofrx     dofry     dofrz
         8         0         1         1         1         1         1         1
*SET_NODE_LIST
         9
         1         2         3         4
*DEFINE_CURVE
$       ID      sidr       sfa       sfo      offa      offo    dattyp   unused1
         2         0         0         0         0         0         0          
$                 a1                  o1                                 unused1
                   0                   0                                        
$                 a1                  o1                                 unused1
                   1                   0                                        
$                 a1                  o1                                 unused1
                  10                   0                                        
*BOUNDARY_PRESCRIBED_MOTION_SET
$      sid       dof       vad      lcid        sf       vid     death     birth
         9         1         2         2         1         0         0         0
*DEFINE_CURVE
$       ID      sidr       sfa       sfo      offa      offo    dattyp   unused1
         3         0         0         0         0         0         0          
$                 a1                  o1                                 unused1
                   0                   0                                        
$                 a1                  o1                                 unused1
                   1                   0                                        
$                 a1                  o1                                 unused1
                  10                   0                                        
*BOUNDARY_PRESCRIBED_MOTION_SET
$      sid       dof       vad      lcid        sf       vid     death     birth
         9         2         2         3         1         0         0         0
*DEFINE_CURVE
$       ID      sidr       sfa       sfo      offa      offo    dattyp   unused1
         4         0         0         0         0         0         0          
$                 a1                  o1                                 unused1
                   0                   0                                        
$                 a1                  o1                                 unused1
                   1              -0.254                                        
$                 a1                  o1                                 unused1
                  10              -0.254                                        
*BOUNDARY_PRESCRIBED_MOTION_SET
$      sid       dof       vad      lcid        sf       vid     death     birth
         9         3         2         4         1         0         0         0
*DATABASE_GLSTAT
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_SPCFORC
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_RCFORC
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_BNDOUT
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_NODOUT
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_MATSUM
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_ELOUT
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_JNTFORC
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_DEFORC
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_TPRINT
$       dt    binary      lcur     ioopt     dthff     binhf             unused1
     0.001         3         0         0         0         0                   0
*DATABASE_EXTENT_BINARY
$    neiph     neips    maxint    strflg    sigflg    epsflg    rltflg    engflg
         0         0         0        10         1         1         0         0
$   cmpflg    ieverp    beamip     dcomp      shge     stssz    n3thdt   ialemat
         0         0         0         0         0         0         0         0
$  nintsld   pkp_sen      sclp     hydro     msscl     therm    intout    nodout
         0         0         0         0         2         0                    
*DATABASE_BINARY_D3PLOT
$       dt      lcdt      beam     npltc    psetid                       unused1
      0.05         0         0         0         0                              
$    ioopt                                                               unused2
         0                                                                      
*DATABASE_BINARY_INTFOR
$       dt      lcdt      beam     npltc    psetid                        unused
      0.05         0         0         0         0                              
*DATABASE_BINARY_D3PROP
$    ifile     imatl     iwall                                           unused2
         2         1         0                                                  
*END
